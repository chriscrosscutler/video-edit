// What makes a frame a good cover, scored by Apple Vision on every `step`-th frame (macOS 12+;
// aesthetics need macOS 15), for cover.py.
// Build once: swiftc -O cover.swift -o ~/.cache/video-edit/cover
// Usage: cover <video> <step> [fps]
// Prints JSON [{"frame": F, "aesthetic": -1..1 or null, "utility": bool or null, "sharpness": S,
//   "faces": [[x0, y0, x1, y1, confidence, left_eye, right_eye, pitch], ...]}, ...]. aesthetic and utility are
// VNCalculateImageAestheticsScoresRequest's overallScore and isUtility (null before macOS 15); sharpness is
// the variance of a Laplacian over the luma plane downsampled to about 360 px, comparable within one
// clip only; an eye is its height over its width from the face landmarks (open about 0.25-0.4, shut
// under 0.15; null when Vision gives no eye); pitch is the head's tilt in radians, positive looking down
// (null when Vision gives none). Face boxes are faces.swift's: fractions of the frame as
// displayed, origin top-left. frame is the presentation frame at `fps` (default 30).
import AVFoundation
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("cover: \(message)\n".utf8))
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

// Measured across the eye's long axis, so a tilted head doesn't read as a wide-open eye.
func openness(_ region: VNFaceLandmarkRegion2D?, _ size: CGSize) -> String {
    guard let region, region.pointCount >= 4 else { return "null" }
    let p = region.pointsInImage(imageSize: size)
    var (a, b, width) = (p[0], p[0], 0.0)
    for i in p.indices { for j in p.indices where j > i {
        let d = hypot(p[i].x - p[j].x, p[i].y - p[j].y)
        if d > width { (a, b, width) = (p[i], p[j], d) }
    } }
    guard width > 0 else { return "null" }
    let (nx, ny) = (-(b.y - a.y) / width, (b.x - a.x) / width)
    let across = p.map { ($0.x - a.x) * nx + ($0.y - a.y) * ny }
    return String(format: "%.3f", (across.max()! - across.min()!) / width)
}

func sharpness(_ pixels: CVPixelBuffer) -> Double {
    CVPixelBufferLockBaseAddress(pixels, .readOnly)
    defer { CVPixelBufferUnlockBaseAddress(pixels, .readOnly) }
    guard let base = CVPixelBufferGetBaseAddressOfPlane(pixels, 0) else { return 0 }
    let luma = base.assumingMemoryBound(to: UInt8.self)
    let (w, h) = (CVPixelBufferGetWidthOfPlane(pixels, 0), CVPixelBufferGetHeightOfPlane(pixels, 0))
    let stride = CVPixelBufferGetBytesPerRowOfPlane(pixels, 0)
    let k = max(1, min(w, h) / 360)  // sensor noise and resolution would swamp a full-size Laplacian
    let (dw, dh) = (w / k, h / k)
    guard dw > 2, dh > 2 else { return 0 }
    var small = [Int](repeating: 0, count: dw * dh)
    for j in 0..<dh {
        for i in 0..<dw {
            var s = 0
            for b in 0..<k {
                let line = luma + (j * k + b) * stride + i * k
                for a in 0..<k { s += Int(line[a]) }
            }
            small[j * dw + i] = s
        }
    }
    var (sum, squares) = (0.0, 0.0)
    for j in 1..<dh - 1 {
        for i in 1..<dw - 1 {
            let c = j * dw + i
            let l = Double(4 * small[c] - small[c - 1] - small[c + 1] - small[c - dw] - small[c + dw]) / Double(k * k)
            sum += l
            squares += l * l
        }
    }
    let count = Double((dw - 2) * (dh - 2))
    return squares / count - (sum / count) * (sum / count)
}

let args = CommandLine.arguments
guard args.count >= 3, let step = Int(args[2]), step > 0 else { fail("usage: cover <video> <step> [fps]") }
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

var rows: [String] = []
var n = 0
while let sample = output.copyNextSampleBuffer() {
    defer { n += 1 }
    guard n % step == 0, let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
    let frame = Int((CMSampleBufferGetPresentationTimeStamp(sample).seconds * fps).rounded())
    var (w, h) = (CVPixelBufferGetWidth(pixels), CVPixelBufferGetHeight(pixels))
    if [.left, .right].contains(orientation) { (w, h) = (h, w) }
    let faces = VNDetectFaceLandmarksRequest()
    var requests: [VNRequest] = [faces]
    var aesthetic = "null", utility = "null"
    autoreleasepool {
        var scores: VNRequest?
        if #available(macOS 15, *) {
            scores = VNCalculateImageAestheticsScoresRequest()
            requests.append(scores!)
        }
        do {
            // rectangles first: revision 3 measures the head's roll, yaw and pitch, which landmarks keep
            let rects = VNDetectFaceRectanglesRequest()
            rects.revision = VNDetectFaceRectanglesRequestRevision3
            let handler = VNImageRequestHandler(cvPixelBuffer: pixels, orientation: orientation, options: [:])
            try handler.perform([rects])
            faces.inputFaceObservations = rects.results ?? []
            try handler.perform(requests)
        } catch {
            fail("Vision failed on frame \(frame): \(error)")
        }
        if #available(macOS 15, *), let s = (scores as? VNCalculateImageAestheticsScoresRequest)?.results?.first {
            aesthetic = String(format: "%.4f", s.overallScore)
            utility = s.isUtility ? "true" : "false"
        }
    }
    let size = CGSize(width: w, height: h)
    let found = (faces.results ?? []).map { face -> String in
        let b = face.boundingBox
        return String(format: "[%.4f,%.4f,%.4f,%.4f,%.3f,", b.minX, 1 - b.maxY, b.maxX, 1 - b.minY, face.confidence)
            + openness(face.landmarks?.leftEye, size) + "," + openness(face.landmarks?.rightEye, size) + ","
            + (face.pitch.map { String(format: "%.3f", $0.doubleValue) } ?? "null") + "]"
    }
    rows.append(String(format: "{\"frame\":%d,\"aesthetic\":%@,\"utility\":%@,\"sharpness\":%.2f,\"faces\":[%@]}",
                       frame, aesthetic, utility, sharpness(pixels), found.joined(separator: ",")))
}
if reader.status == .failed { fail("decode failed: \(reader.error?.localizedDescription ?? "?")") }
print("[" + rows.joined(separator: ",") + "]")
