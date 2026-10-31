// Person matte by Apple Vision person segmentation (macOS 12+), for text behind a person; --subject
// mattes any foreground subject instead (a product, a pet, a hand: subject lifting, macOS 14+).
// Build once: swiftc -O matte.swift -o ~/.cache/video-edit/matte
// Usage: matte <video> <mask.mp4> [--person person.webm] [--quality accurate|balanced|fast]
//              [--subject all|X,Y]
// Writes a grey matte the size and frame count of the video, white where a person is (lossless
// H.264, full range); --person also writes the video cut out on VP9 alpha, edge softened, for
// Remotion. --subject all mattes every foreground instance; --subject X,Y (fractions, origin top-left)
// only the instance under that point on each frame, holding the last matte while the point is on
// background. --quality is for the person matte only. Run it on the cut (a draft render), not the
// sources. Needs ffmpeg on PATH.
import AVFoundation
import CoreImage
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("matte: \(message)\n".utf8))
    exit(1)
}

var args = Array(CommandLine.arguments.dropFirst())
func option(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name) else { return nil }
    guard i + 1 < args.count else { fail("\(name) needs a value") }
    defer { args.removeSubrange(i...i + 1) }
    return args[i + 1]
}
let personPath = option("--person")
let qualities: [String: VNGeneratePersonSegmentationRequest.QualityLevel] = [
    "accurate": .accurate, "balanced": .balanced, "fast": .fast,
]
guard let quality = qualities[option("--quality") ?? "accurate"] else { fail("--quality is accurate, balanced or fast") }
let subject = option("--subject")
var point: CGPoint?
if let s = subject, s != "all" {
    let v = s.split(separator: ",").compactMap { Double($0) }
    guard v.count == 2, (0...1).contains(v[0]), (0...1).contains(v[1]) else {
        fail("--subject is all or X,Y in fractions of the frame")
    }
    point = CGPoint(x: v[0], y: v[1])
}
guard args.count == 2 else {
    fail("usage: matte <video> <mask.mp4> [--person person.webm] [--quality accurate|balanced|fast] "
         + "[--subject all|X,Y]")
}
let (videoPath, maskPath) = (args[0], args[1])
guard FileManager.default.fileExists(atPath: videoPath) else { fail("no such file: \(videoPath)") }

let asset = AVURLAsset(url: URL(fileURLWithPath: videoPath))
guard let track = asset.tracks(withMediaType: .video).first else { fail("no video track in \(videoPath)") }
if track.preferredTransform != .identity { fail("\(videoPath) is rotated: conform it first (edl.py conform)") }
let step = track.minFrameDuration
guard step.isValid, step.value > 0 else { fail("no frame rate in \(videoPath)") }
guard let reader = try? AVAssetReader(asset: asset) else { fail("can't read \(videoPath)") }
let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
])
output.alwaysCopiesSampleData = false
reader.add(output)
reader.startReading()

// ffmpeg takes raw grey frames on stdin; with --person it also reads the video for the cutout.
func ffmpegArgs(_ w: Int, _ h: Int) -> [String] {
    let mask = ["-c:v", "libx264", "-qp", "0", "-pix_fmt", "gray", "-color_range", "pc", "-an", maskPath]
    var a = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-video_size", "\(w)x\(h)",
             "-r", "\(step.timescale)/\(step.value)", "-i", "-"]
    guard let person = personPath else { return a + mask }
    a += ["-i", videoPath, "-filter_complex",
          "[0:v]split[raw][a];[a]tmedian=radius=1,gblur=sigma=1.5[soft];"
              + "[1:v]setpts=PTS-STARTPTS,format=yuva420p[v];[v][soft]alphamerge,"
              + "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv[p]",
          "-map", "[raw]"] + mask
    return a + ["-map", "[p]", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
                "-crf", "18", "-b:v", "0", "-row-mt", "1", "-cpu-used", "4", "-an", person]
}

signal(SIGPIPE, SIG_IGN)  // a dead ffmpeg surfaces as a write error, not a silent exit
let ffmpeg = Process()
let pipe = Pipe()
ffmpeg.executableURL = URL(fileURLWithPath: "/usr/bin/env")
ffmpeg.standardInput = pipe

let request = VNGeneratePersonSegmentationRequest()
request.qualityLevel = quality
request.outputPixelFormat = kCVPixelFormatType_OneComponent8
let sequence = VNSequenceRequestHandler()  // one handler across frames keeps the matte steady
let context = CIContext(options: [.workingColorSpace: NSNull(), .outputColorSpace: NSNull()])
var (w, h, n, found) = (0, 0, 0, 0)
var first = CMTime.zero
var grey: [UInt8] = []

// A low-resolution float or byte matte, stretched to the frame into grey.
func render(_ buffer: CVPixelBuffer) {
    let m = CIImage(cvPixelBuffer: buffer, options: [.colorSpace: NSNull()])
    let frame = CGRect(x: 0, y: 0, width: w, height: h)
    let fit = CGAffineTransform(scaleX: CGFloat(w) / m.extent.width, y: CGFloat(h) / m.extent.height)
    context.render(m.clampedToExtent().transformed(by: fit).cropped(to: frame), toBitmap: &grey,
                   rowBytes: w, bounds: frame, format: .L8, colorSpace: nil)
}

// Subject lifting: every instance, or the one under the point; false leaves grey as it was.
func subjectMatte(_ pixels: CVPixelBuffer) -> Bool {
    guard #available(macOS 14, *) else { fail("--subject needs macOS 14") }
    let request = VNGenerateForegroundInstanceMaskRequest()
    do {
        try VNImageRequestHandler(cvPixelBuffer: pixels, options: [:]).perform([request])
    } catch {
        fail("Vision failed on frame \(n): \(error)")
    }
    guard let result = request.results?.first else { return false }
    var instances = result.allInstances
    if let p = point {
        let labels = result.instanceMask
        CVPixelBufferLockBaseAddress(labels, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(labels, .readOnly) }
        let (lw, lh) = (CVPixelBufferGetWidth(labels), CVPixelBufferGetHeight(labels))
        guard let base = CVPixelBufferGetBaseAddress(labels) else { return false }
        let label = base.assumingMemoryBound(to: UInt8.self)[
            min(lh - 1, Int(p.y * Double(lh))) * CVPixelBufferGetBytesPerRow(labels) + min(lw - 1, Int(p.x * Double(lw)))]
        if label == 0 { return false }
        instances = IndexSet(integer: Int(label))
    }
    guard !instances.isEmpty, let mask = try? result.generateMask(forInstances: instances) else { return false }
    render(mask)
    return true
}

while let sample = output.copyNextSampleBuffer() {
    guard let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
    let pts = CMSampleBufferGetPresentationTimeStamp(sample)
    if n == 0 {
        (w, h, first) = (CVPixelBufferGetWidth(pixels), CVPixelBufferGetHeight(pixels), pts)
        grey = [UInt8](repeating: 0, count: w * h)
        ffmpeg.arguments = ffmpegArgs(w, h)
        do { try ffmpeg.run() } catch { fail("can't start ffmpeg: \(error)") }
    } else if abs((pts - first).seconds / step.seconds - Double(n)) > 0.5 {
        fail("frame \(n) is off the \(Int((1 / step.seconds).rounded())) fps grid: conform to a constant rate first")
    }
    autoreleasepool {
        if subject != nil {
            if !subjectMatte(pixels) && point == nil { grey = [UInt8](repeating: 0, count: w * h) }
            if grey.contains(where: { $0 > 127 }) { found += 1 }
            return
        }
        do {
            try sequence.perform([request], on: pixels)
        } catch {
            fail("Vision failed on frame \(n): \(error)")
        }
        if let buffer = request.results?.first?.pixelBuffer {
            render(buffer)
            if grey.contains(where: { $0 > 127 }) { found += 1 }
        } else {
            grey = [UInt8](repeating: 0, count: w * h)
        }
    }
    do {
        try pipe.fileHandleForWriting.write(contentsOf: Data(grey))
    } catch {
        ffmpeg.waitUntilExit()
        fail("ffmpeg stopped at frame \(n) (exit \(ffmpeg.terminationStatus))")
    }
    n += 1
}
if reader.status == .failed { fail("decode failed: \(reader.error?.localizedDescription ?? "?")") }
if n == 0 { fail("no frames in \(videoPath)") }
try? pipe.fileHandleForWriting.close()
ffmpeg.waitUntilExit()
if ffmpeg.terminationStatus != 0 { fail("ffmpeg exited \(ffmpeg.terminationStatus)") }
print("\(maskPath): \(n) frames \(w)x\(h), a \(subject == nil ? "person" : "subject") in \(found)"
      + (personPath.map { "; \($0)" } ?? ""))
