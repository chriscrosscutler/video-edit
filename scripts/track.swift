// Follows a box through a video with Apple Vision object tracking (macOS 12+), for redact.py --track
// and anything that has to stay on a moving thing.
// Build once: swiftc -O track.swift -o ~/.cache/video-edit/track
// Usage: track <video> <start_frame> <x0,y0,x1,y1> [--to END_FRAME] [--fps 30]
// Prints JSON [[frame, [x0, y0, x1, y1, confidence]], ...] for every frame from start_frame to END_FRAME
// (default: the end), or until the confidence stays under 0.3 for a third of a second, which stderr
// reports; that low stretch is left out. Coordinates are fractions of the frame as displayed (rotation
// applied), origin top-left; frames are presentation frames at --fps. Tracking runs forward only:
// start on the first frame the thing is fully in view.
import AVFoundation
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("track: \(message)\n".utf8))
    exit(1)
}

func upright(_ t: CGAffineTransform) -> CGImagePropertyOrientation {
    switch (t.a, t.b, t.c, t.d) {
    case (0, 1, -1, 0): return .right
    case (0, -1, 1, 0): return .left
    case (-1, 0, 0, -1): return .down
    default: return .up
    }
}

let usage = "usage: track <video> <start_frame> <x0,y0,x1,y1> [--to END_FRAME] [--fps 30]"
var args = Array(CommandLine.arguments.dropFirst())
func option(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name) else { return nil }
    guard i + 1 < args.count else { fail("\(name) needs a value") }
    defer { args.removeSubrange(i...i + 1) }
    return args[i + 1]
}
var end: Int?
if let s = option("--to") {
    guard let e = Int(s) else { fail("--to takes a frame number") }
    end = e
}
var fps = 30.0
if let s = option("--fps") {
    guard let f = Double(s), f > 0 else { fail("--fps takes a number") }
    fps = f
}
guard args.count == 3, let start = Int(args[1]) else { fail(usage) }
let v = args[2].split(separator: ",").compactMap { Double($0) }
guard v.count == 4, 0 <= v[0], v[0] < v[2], v[2] <= 1, 0 <= v[1], v[1] < v[3], v[3] <= 1 else {
    fail("the box is x0,y0,x1,y1 in fractions of the frame, origin top-left")
}

let asset = AVURLAsset(url: URL(fileURLWithPath: args[0]))
guard let track = asset.tracks(withMediaType: .video).first else { fail("no video track in \(args[0])") }
let orientation = upright(track.preferredTransform)
guard let reader = try? AVAssetReader(asset: asset) else { fail("can't read \(args[0])") }
let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
])
output.alwaysCopiesSampleData = false
reader.add(output)
reader.startReading()

func row(_ frame: Int, _ b: CGRect, _ confidence: Float) -> String {
    String(format: "[%d,[%.4f,%.4f,%.4f,%.4f,%.3f]]", frame, b.minX, 1 - b.maxY, b.maxX, 1 - b.minY, confidence)
}

let sequence = VNSequenceRequestHandler()
// The first perform, on the start frame itself, is where the tracker learns what the box holds.
let request = VNTrackObjectRequest(detectedObjectObservation: VNDetectedObjectObservation(
    boundingBox: CGRect(x: v[0], y: 1 - v[3], width: v[2] - v[0], height: v[3] - v[1])))
request.trackingLevel = .accurate
let patience = max(3, Int((fps / 3).rounded()))
var rows: [String] = []
var low: [String] = []  // a dip is kept if the track recovers, dropped if it is lost
var lost: Int?
var seen = false
while let sample = output.copyNextSampleBuffer() {
    guard let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
    let frame = Int((CMSampleBufferGetPresentationTimeStamp(sample).seconds * fps).rounded())
    if frame < start { continue }
    if let end, frame > end { break }
    seen = true
    let result: VNDetectedObjectObservation? = autoreleasepool {
        do {
            try sequence.perform([request], on: pixels, orientation: orientation)
        } catch {
            fail("Vision failed on frame \(frame): \(error)")
        }
        return request.results?.first as? VNDetectedObjectObservation
    }
    guard let found = result else { fail("no tracking result on frame \(frame)") }
    request.inputObservation = found
    if found.confidence < 0.3 {
        low.append(row(frame, found.boundingBox, found.confidence))
        if low.count >= patience {
            lost = frame - patience + 1
            break
        }
    } else {
        rows += low
        low = []
        rows.append(row(frame, found.boundingBox, found.confidence))
    }
}
if reader.status == .failed { fail("decode failed: \(reader.error?.localizedDescription ?? "?")") }
if !seen { fail("no frame \(start) in \(args[0]) at \(fps) fps") }
if let lost { FileHandle.standardError.write(Data("track: lost at frame \(lost)\n".utf8)) }
print("[" + rows.joined(separator: ",") + "]")
