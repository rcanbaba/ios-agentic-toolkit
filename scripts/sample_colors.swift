// Sample dominant colors from reference screenshots.
//
// Deterministic measurement step of the design-system workflow: the agent
// interprets screenshots visually, but hex values come from pixels, not guesses.
//
// Usage: swift sample_colors.swift [--k <clusters>] <image> [<image> ...]
// Output: JSON array, one entry per image:
//   { "file", "width_px", "height_px", "assumed_scale", "width_pt",
//     "colors": [ { "hex", "coverage" } ] }   // sorted by coverage, descending
//
// Images are downsampled to 160px wide and clustered with k-means
// (deterministic initialization); each cluster reports its most frequent exact
// pixel color. Tiny details (thin text, icons) may not appear; crop the region
// of interest for those.

import CoreGraphics
import Foundation
import ImageIO

struct RGB { var r: Double; var g: Double; var b: Double }

func loadPixels(_ path: String, targetWidth: Int) -> (pixels: [RGB], width: Int, height: Int)? {
    let url = URL(fileURLWithPath: path)
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { return nil }
    let w = targetWidth
    let h = max(1, Int(Double(image.height) * Double(w) / Double(image.width)))
    var buffer = [UInt8](repeating: 0, count: w * h * 4)
    guard let context = CGContext(
        data: &buffer, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { return nil }
    context.interpolationQuality = .medium
    context.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
    var pixels: [RGB] = []
    pixels.reserveCapacity(w * h)
    for i in stride(from: 0, to: buffer.count, by: 4) where buffer[i + 3] > 0 {
        pixels.append(RGB(r: Double(buffer[i]), g: Double(buffer[i + 1]), b: Double(buffer[i + 2])))
    }
    return (pixels, image.width, image.height)
}

func distance(_ a: RGB, _ b: RGB) -> Double {
    let dr = a.r - b.r, dg = a.g - b.g, db = a.b - b.b
    return dr * dr + dg * dg + db * db
}

func luminance(_ c: RGB) -> Double { 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b }

func kMeans(_ pixels: [RGB], k: Int, iterations: Int = 12) -> [(RGB, Int)] {
    guard !pixels.isEmpty else { return [] }
    // Deterministic init: centroids at luminance quantiles.
    let sorted = pixels.sorted { luminance($0) < luminance($1) }
    var centroids: [RGB] = []
    for j in 0..<k {
        let index: Int = (j * 2 + 1) * sorted.count / (2 * k)
        centroids.append(sorted[min(sorted.count - 1, index)])
    }
    var assignment = [Int](repeating: 0, count: pixels.count)
    for _ in 0..<iterations {
        for (i, p) in pixels.enumerated() {
            var best = 0
            var bestDistance = Double.infinity
            for (j, c) in centroids.enumerated() {
                let d = distance(p, c)
                if d < bestDistance { bestDistance = d; best = j }
            }
            assignment[i] = best
        }
        var sums = [RGB](repeating: RGB(r: 0, g: 0, b: 0), count: k)
        var counts = [Int](repeating: 0, count: k)
        for (i, p) in pixels.enumerated() {
            let j = assignment[i]
            sums[j].r += p.r; sums[j].g += p.g; sums[j].b += p.b
            counts[j] += 1
        }
        for j in 0..<k where counts[j] > 0 {
            centroids[j] = RGB(r: sums[j].r / Double(counts[j]), g: sums[j].g / Double(counts[j]), b: sums[j].b / Double(counts[j]))
        }
    }
    // Report the most frequent exact pixel color in each cluster rather than the
    // mean, so flat UI colors come out exact instead of blended with anti-aliasing.
    var counts = [Int](repeating: 0, count: k)
    var frequencies = [[UInt32: Int]](repeating: [:], count: k)
    for (i, p) in pixels.enumerated() {
        let j = assignment[i]
        counts[j] += 1
        let key = UInt32(p.r) << 16 | UInt32(p.g) << 8 | UInt32(p.b)
        frequencies[j][key, default: 0] += 1
    }
    var result: [(RGB, Int)] = []
    for j in 0..<k where counts[j] > 0 {
        let mode = frequencies[j].max { $0.value < $1.value }!.key
        let color = RGB(r: Double(mode >> 16 & 0xFF), g: Double(mode >> 8 & 0xFF), b: Double(mode & 0xFF))
        result.append((color, counts[j]))
    }
    return result.sorted { $0.1 > $1.1 }
}

func hex(_ c: RGB) -> String {
    String(format: "#%02X%02X%02X", Int(c.r.rounded()), Int(c.g.rounded()), Int(c.b.rounded()))
}

// Common iPhone screenshot widths in pixels at @3x / @2x.
func assumedScale(widthPx: Int) -> Int {
    let threeX: Set<Int> = [1080, 1125, 1170, 1179, 1206, 1242, 1260, 1284, 1290, 1320]
    let twoX: Set<Int> = [640, 750, 828]
    if threeX.contains(widthPx) { return 3 }
    if twoX.contains(widthPx) { return 2 }
    return widthPx >= 1000 ? 3 : 2
}

var args = Array(CommandLine.arguments.dropFirst())
var k = 8
if let i = args.firstIndex(of: "--k"), i + 1 < args.count, let value = Int(args[i + 1]) {
    k = max(2, min(value, 16))
    args.removeSubrange(i...(i + 1))
}
guard !args.isEmpty else {
    FileHandle.standardError.write("usage: swift sample_colors.swift [--k <clusters>] <image> [<image> ...]\n".data(using: .utf8)!)
    exit(2)
}

var results: [[String: Any]] = []
for path in args {
    guard let (pixels, w, h) = loadPixels(path, targetWidth: 160) else {
        results.append(["file": path, "error": "could not read image"])
        continue
    }
    let clusters = kMeans(pixels, k: k)
    let total = Double(pixels.count)
    let scale = assumedScale(widthPx: w)
    results.append([
        "file": path,
        "width_px": w,
        "height_px": h,
        "assumed_scale": scale,
        "width_pt": w / scale,
        "colors": clusters.map { ["hex": hex($0.0), "coverage": NSDecimalNumber(string: String(format: "%.3f", Double($0.1) / total))] },
    ])
}

let data = try JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted, .sortedKeys])
print(String(data: data, encoding: .utf8)!)
