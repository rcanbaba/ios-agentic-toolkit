// Draws the VNCBar app icon (1024×1024 PNG): a "C" arc around a small screen, with a connection
// dot in its opening, on the macOS icon grid (824 pt body, 100 pt margin).
// Usage: swift Icon/make-icon.swift <out.png>
import AppKit

let side = 1024
guard CommandLine.arguments.count == 2,
      let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: side, pixelsHigh: side, bitsPerSample: 8,
                                 samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                 bytesPerRow: 0, bitsPerPixel: 0),
      let context = NSGraphicsContext(bitmapImageRep: rep) else {
    print("usage: make-icon.swift <out.png>")
    exit(2)
}
let ctx = context.cgContext
func rgb(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: r, green: g, blue: b, alpha: a)
}
let space = CGColorSpace(name: CGColorSpace.sRGB)!

// Body with a soft drop shadow.
let body = CGRect(x: 100, y: 100, width: 824, height: 824)
let shape = CGPath(roundedRect: body, cornerWidth: 185, cornerHeight: 185, transform: nil)
ctx.saveGState()
ctx.setShadow(offset: CGSize(width: 0, height: -14), blur: 34, color: rgb(0, 0, 0, 0.35))
ctx.addPath(shape)
ctx.setFillColor(rgb(0.1, 0.12, 0.3))
ctx.fillPath()
ctx.restoreGState()

// Indigo → teal background, plus a faint highlight at the top.
ctx.saveGState()
ctx.addPath(shape)
ctx.clip()
let background = CGGradient(colorsSpace: space, colors: [rgb(0.15, 0.17, 0.52), rgb(0.03, 0.58, 0.74)] as CFArray,
                            locations: [0, 1])!
ctx.drawLinearGradient(background, start: CGPoint(x: 180, y: 924), end: CGPoint(x: 844, y: 100), options: [])
let shine = CGGradient(colorsSpace: space, colors: [rgb(1, 1, 1, 0.16), rgb(1, 1, 1, 0)] as CFArray, locations: [0, 1])!
ctx.drawLinearGradient(shine, start: CGPoint(x: 512, y: 924), end: CGPoint(x: 512, y: 560), options: [])
ctx.restoreGState()

let center = CGPoint(x: 512, y: 512)
let radius: CGFloat = 250

// The "C": a thick arc open to the right.
ctx.saveGState()
ctx.setShadow(offset: CGSize(width: 0, height: -6), blur: 16, color: rgb(0, 0, 0, 0.25))
ctx.setLineWidth(118)
ctx.setLineCap(.round)
ctx.setStrokeColor(rgb(1, 1, 1))
ctx.addArc(center: center, radius: radius, startAngle: .pi * 0.25, endAngle: -.pi * 0.25, clockwise: false)
ctx.strokePath()
ctx.restoreGState()

// A small screen on a stand inside the C.
ctx.setStrokeColor(rgb(1, 1, 1, 0.95))
ctx.setFillColor(rgb(1, 1, 1, 0.95))
ctx.setLineWidth(20)
ctx.setLineCap(.round)
let screen = CGRect(x: center.x - 112, y: center.y - 40, width: 196, height: 128)
ctx.addPath(CGPath(roundedRect: screen, cornerWidth: 20, cornerHeight: 20, transform: nil))
ctx.strokePath()
ctx.move(to: CGPoint(x: screen.midX, y: screen.minY - 6))
ctx.addLine(to: CGPoint(x: screen.midX, y: screen.minY - 42))
ctx.move(to: CGPoint(x: screen.midX - 48, y: screen.minY - 52))
ctx.addLine(to: CGPoint(x: screen.midX + 48, y: screen.minY - 52))
ctx.strokePath()

// The connection dot in the C's opening, glowing.
let dot = CGPoint(x: center.x + radius, y: center.y)
let glow = CGGradient(colorsSpace: space, colors: [rgb(0.55, 1, 0.85, 0.75), rgb(0.55, 1, 0.85, 0)] as CFArray,
                      locations: [0, 1])!
ctx.drawRadialGradient(glow, startCenter: dot, startRadius: 0, endCenter: dot, endRadius: 120, options: [])
ctx.setFillColor(rgb(0.62, 1, 0.86))
ctx.fillEllipse(in: CGRect(x: dot.x - 46, y: dot.y - 46, width: 92, height: 92))

guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
