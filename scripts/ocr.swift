// Text lines and barcodes found by Apple Vision on every `step`-th frame of a video (macOS 12+),
// for redact.py and edl.py qa.
// Build once: swiftc -O ocr.swift -o ~/.cache/video-edit/ocr
// Usage: ocr <video> <step> [fps]
// Prints JSON [[frame, [[x0, y0, x1, y1, confidence, "text"], ...]], ...]: one box per text line and per
// barcode, whose text is "barcode:<payload>". Recognition is accurate with language correction off, so
// codes and numbers come through as printed. Coordinates are fractions of the frame as displayed
// (rotation applied, as ffmpeg shows it), origin top-left; frame is the presentation frame at `fps`
// (default 30).
import AVFoundation
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("ocr: \(message)\n".utf8))
    exit(1)
}

// Vision reads the frame upright, so its boxes match the autorotated frame ffmpeg filters.
func upright(_ t: CGAffineTransform) -> CGImagePropertyOrientation {
    switch (t.a, t.b, t.c, t.d) {
    case (0, 1, -1, 0): return .right
    case (0, -1, 1, 0): return .left
    case (-1, 0, 0, -1): return .down
    default: return .up
    }
}

let args = CommandLine.arguments
guard args.count >= 3, let step = Int(args[2]), step > 0 else { fail("usage: ocr <video> <step> [fps]") }
let fps = args.count > 3 ? Double(args[3]) ?? 30 : 30
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
guard let track = asset.tracks(withMediaType: .video).first else { fail("no video track in \(args[1])") }
let orientation = upright(track.preferredTransform)
guard let reader = try? AVAssetReader(asset: asset) else { fail("can't read \(args[1])") }
let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
])
output.alwaysCopiesSampleData = false
reader.add(output)
reader.startReading()

let encoder = JSONEncoder()
encoder.outputFormatting = .withoutEscapingSlashes
func row(_ b: CGRect, _ confidence: Float, _ text: String) -> String {
    let quoted = (try? encoder.encode(text)).map { String(decoding: $0, as: UTF8.self) } ?? "\"\""
    return String(format: "[%.4f,%.4f,%.4f,%.4f,%.3f,", b.minX, 1 - b.maxY, b.maxX, 1 - b.minY, confidence)
        + quoted + "]"
}

var rows: [String] = []
var n = 0
while let sample = output.copyNextSampleBuffer() {
    defer { n += 1 }
    guard n % step == 0, let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
    let frame = Int((CMSampleBufferGetPresentationTimeStamp(sample).seconds * fps).rounded())
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.usesLanguageCorrection = false
    text.minimumTextHeight = 0.012  // the default (1/32 of the height) misses a label's small print
    let codes = VNDetectBarcodesRequest()
    autoreleasepool {
        do {
            try VNImageRequestHandler(cvPixelBuffer: pixels, orientation: orientation, options: [:])
                .perform([text, codes])
        } catch {
            fail("Vision failed on frame \(frame): \(error)")
        }
    }
    var found = (text.results ?? []).compactMap { line -> String? in
        guard let best = line.topCandidates(1).first else { return nil }
        return row(line.boundingBox, best.confidence, best.string)  // boundingBox: normalised, origin bottom-left
    }
    found += (codes.results ?? []).map {
        row($0.boundingBox, $0.confidence, "barcode:" + ($0.payloadStringValue ?? ""))
    }
    rows.append("[\(frame),[\(found.joined(separator: ","))]]")
}
if reader.status == .failed { fail("decode failed: \(reader.error?.localizedDescription ?? "?")") }
print("[" + rows.joined(separator: ",") + "]")
