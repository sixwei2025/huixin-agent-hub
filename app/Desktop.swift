import AppKit
import WebKit

final class HubDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var server: Process?
    var fileWindows: [NSWindow] = []
    let targetVersion = "0.4.0"
    let address = URL(string: "http://127.0.0.1:39261/")!
    let healthAddress = URL(string: "http://127.0.0.1:39261/api/health")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let iconURL = Bundle.main.url(forResource: "AppIcon", withExtension: "icns"),
           let icon = NSImage(contentsOf: iconURL) {
            NSApp.applicationIconImage = icon
        }
        let menu = NSMenu()
        let appItem = NSMenuItem()
        menu.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "退出汇芯智能体中台", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        let editItem = NSMenuItem(title: "编辑", action: nil, keyEquivalent: "")
        let editMenu = NSMenu(title: "编辑")
        for (title, action, key) in [("撤销", "undo:", "z"), ("剪切", "cut:", "x"), ("复制", "copy:", "c"), ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        editItem.submenu = editMenu
        menu.addItem(editItem)
        NSApp.mainMenu = menu
        let configuration = WKWebViewConfiguration()
        configuration.applicationNameForUserAgent = "HuixinDesktop/0.2"
        configuration.websiteDataStore = .default()
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.uiDelegate = self
        webView.navigationDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1380, height: 860), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.delegate = self
        window.title = "汇芯智能体中台"
        window.minSize = NSSize(width: 900, height: 630)
        window.backgroundColor = NSColor(calibratedWhite: 0.975, alpha: 1)
        window.contentView = webView
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        webView.loadHTMLString("<html lang='zh-CN'><body style='background:#f8f8fa;font-family:-apple-system;text-align:center;padding-top:30vh;color:#888'><h2 style='color:#333;font-weight:500'>汇芯智能体中台</h2><p>正在连接本机工作区…</p></body></html>", baseURL: nil)
        connect(attempt: 0)
    }

    func connect(attempt: Int) {
        var request = URLRequest(url: healthAddress)
        request.setValue("HuixinDesktop/0.3", forHTTPHeaderField: "User-Agent")
        request.timeoutInterval = 1
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if let data = data,
                   let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let ver = obj["version"] as? String, ver == self.targetVersion {
                    self.webView.load(URLRequest(url: self.address))
                    return
                }
                if attempt == 0 { self.startServer() }
                if attempt < 45 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.connect(attempt: attempt + 1) }
                } else {
                    self.webView.loadHTMLString("<html lang='zh-CN'><body style='font-family:-apple-system;text-align:center;padding-top:28vh'><h2>本机工作区未能启动</h2><p>请确认 Python 3 已安装，且 39261 端口未被旧版本或其他应用占用。</p><p>可查看 ~/.local/share/huixin-agent-hub/server.log 排查，或退出后重新打开重试。</p></body></html>", baseURL: nil)
                }
            }
        }.resume()
    }

    func startServer() {
        guard let script = Bundle.main.url(forResource: "server", withExtension: "py") else { return }
        let logDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/share/huixin-agent-hub")
        try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
        let logURL = logDir.appendingPathComponent("server.log")
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        let logHandle = try? FileHandle(forWritingTo: logURL)
        logHandle?.seekToEndOfFile()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [script.path]
        process.standardOutput = logHandle ?? FileHandle.nullDevice
        process.standardError = logHandle ?? FileHandle.nullDevice
        do { try process.run(); server = process } catch { }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.host == "127.0.0.1" && url.port == 39261 || url.scheme == "about" {
            decisionHandler(.allow)
        } else {
            if navigationAction.navigationType == .linkActivated { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        guard let url = navigationAction.request.url, url.host == "127.0.0.1", url.port == 39261 else { return nil }
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = self
        let fileWindow = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 900, height: 680), styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        fileWindow.title = url.lastPathComponent
        fileWindow.isReleasedWhenClosed = false
        fileWindow.contentView = view
        fileWindow.center()
        fileWindow.makeKeyAndOrderFront(nil)
        fileWindows.append(fileWindow)
        return view
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if sender == window {
            sender.orderOut(nil)
            return false
        }
        return true
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { window.makeKeyAndOrderFront(nil) }
        return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationWillTerminate(_ notification: Notification) {
        if server?.isRunning == true { server?.terminate() }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = HubDelegate()
app.delegate = delegate
app.run()
