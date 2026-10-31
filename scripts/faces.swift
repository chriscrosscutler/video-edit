// Face boxes found by Apple Vision on every `step`-th frame of a video (macOS 12+), for place.py.
// Build once: swiftc -O faces.swift -o ~/.cache/video-edit/faces
// Usage: faces <video> <step> [fps]
// Prints JSON [[frame, [[x0, y0, x1, y1, confidence], ...]], ...]: coordinates are fractions
// of the frame, origin top-left; frame is the presentation frame at `fps` (default 30).
import AVFoundation
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("faces: \(message)\n".utf8))
    exit(1)
}

let args = CommandLine.arguments
guard args.count >= 3, let step = Int(args[2]), step > 0 else { fail("usage: faces <video> <step> [fps]") }
let fps = args.count > 3 ? Double(args[3]) ?? 30 : 30
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
guard let track = asset.tracks(withMediaType: .video).first else { fail("no video track in \(args[1])") }
guard let reader = try? AVAssetReader(asset: asset) else { fail("can't read \(args[1])") }
let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
])
output.alwaysCopiesSampleData = false
reader.add(output)
reader.startReading()

var rows: [String] = []
var n = 0
while let sample = output.copyNextSampleBuffer() {
    defer { n += 1 }
    guard n % step == 0, let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
    let frame = Int((CMSampleBufferGetPresentationTimeStamp(sample).seconds * fps).rounded())
    let request = VNDetectFaceRectanglesRequest()
    do {
        try VNImageRequestHandler(cvPixelBuffer: pixels, options: [:]).perform([request])
    } catch {
        fail("Vision failed on frame \(frame): \(error)")
    }
    let faces = (request.results ?? []).map { face -> String in
        let b = face.boundingBox  // normalised, origin bottom-left
        return String(format: "[%.4f,%.4f,%.4f,%.4f,%.3f]",
                      b.minX, 1 - b.maxY, b.maxX, 1 - b.minY, face.confidence)
    }
    rows.append("[\(frame),[\(faces.joined(separator: ","))]]")
}
if reader.status == .failed { fail("decode failed: \(reader.error?.localizedDescription ?? "?")") }
print("[" + rows.joined(separator: ",") + "]")
