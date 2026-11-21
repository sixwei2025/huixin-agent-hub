import AppKit
let folder = CommandLine.arguments[1]
try FileManager.default.createDirectory(atPath: folder, withIntermediateDirectories: true)
for size in [16,32,64,128,256,512,1024] {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let s = CGFloat(size)
    let margin = s * (100.0 / 1024.0)
    let box = s - margin * 2
    let scale = box / 128.0
    var transform = AffineTransform(translationByX: margin, byY: margin)
    transform.scale(scale)

    NSGraphicsContext.current?.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(white: 0, alpha: 0.16)
    shadow.shadowOffset = NSSize(width: 0, height: -s * 0.012)
    shadow.shadowBlurRadius = s * 0.025
    shadow.set()

    NSColor.white.setFill()
    let bg = NSBezierPath(roundedRect: NSRect(x: margin, y: margin, width: box, height: box), xRadius: box * 0.2237, yRadius: box * 0.2237)
    bg.fill()
    NSGraphicsContext.current?.restoreGraphicsState()

    NSColor(white: 0, alpha: 0.07).setStroke()
    bg.lineWidth = max(0.5, s * 0.002)
    bg.stroke()

    let p = NSBezierPath()
    p.move(to:NSPoint(x:64,y:64))
    p.curve(to:NSPoint(x:31,y:39),controlPoint1:NSPoint(x:49,y:45),controlPoint2:NSPoint(x:42,y:39))
    p.curve(to:NSPoint(x:11,y:64),controlPoint1:NSPoint(x:16,y:39),controlPoint2:NSPoint(x:11,y:51))
    p.curve(to:NSPoint(x:31,y:89),controlPoint1:NSPoint(x:11,y:77),controlPoint2:NSPoint(x:16,y:89))
    p.curve(to:NSPoint(x:64,y:64),controlPoint1:NSPoint(x:42,y:89),controlPoint2:NSPoint(x:49,y:83))
    p.curve(to:NSPoint(x:97,y:39),controlPoint1:NSPoint(x:79,y:45),controlPoint2:NSPoint(x:86,y:39))
    p.curve(to:NSPoint(x:117,y:64),controlPoint1:NSPoint(x:112,y:39),controlPoint2:NSPoint(x:117,y:51))
    p.curve(to:NSPoint(x:97,y:89),controlPoint1:NSPoint(x:117,y:77),controlPoint2:NSPoint(x:112,y:89))
    p.curve(to:NSPoint(x:64,y:64),controlPoint1:NSPoint(x:86,y:89),controlPoint2:NSPoint(x:79,y:83))
    p.close();p.transform(using:transform);p.lineWidth=10*scale;p.lineCapStyle = .round;p.lineJoinStyle = .round
    NSColor(srgbRed:199/255,green:53/255,blue:60/255,alpha:1).setStroke();p.stroke()
    NSGraphicsContext.restoreGraphicsState()
    let png=rep.representation(using:.png,properties:[:])!
    let names:[String]
    switch size {
    case 16:names=["icon_16x16.png"]
    case 32:names=["icon_16x16@2x.png","icon_32x32.png"]
    case 64:names=["icon_32x32@2x.png"]
    case 128:names=["icon_128x128.png"]
    case 256:names=["icon_128x128@2x.png","icon_256x256.png"]
    case 512:names=["icon_256x256@2x.png","icon_512x512.png"]
    default:names=["icon_512x512@2x.png"]
    }
    for name in names {try png.write(to:URL(fileURLWithPath:folder).appendingPathComponent(name))}
}
