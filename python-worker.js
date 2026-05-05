importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js");

self.micropipIncludePre = false;
self.pythonModuleName = null;
self.initialized = false;
self.flet_js = {}; // namespace for Python global functions

self.initPyodide = async function () {
    self.pyodide = await loadPyodide();
    self.pyodide.registerJsModule("flet_js", flet_js);
    flet_js.documentUrl = documentUrl;
    await self.pyodide.loadPackage("micropip");
    let pre = self.micropipIncludePre ? "True" : "False";
    await self.pyodide.runPythonAsync(`
    import micropip
    import os
    from pyodide.http import pyfetch
    response = await pyfetch("app.tar.gz")
    await response.unpack_archive()
    if os.path.exists("requirements.txt"):
        with open("requirements.txt", "r") as f:
            deps = [line.rstrip() for line in f]
            print("Loading requirements.txt:", deps)
            await micropip.install(deps, pre=${pre})
  `);
    pyodide.pyimport(self.pythonModuleName);
    const startFn = self.flet_js.start_connection || self.flet_js.connect || self.flet_js.jsConnect;
    if (!startFn) {
        console.error("No start/connect function on flet_js", Object.keys(self.flet_js));
        throw new Error("No start/connect function on flet_js");
    }
    await startFn(self.receiveCallback);
    self.postMessage("initialized");
};

self.receiveCallback = (message) => {
    self.postMessage(message);
}

self.onmessage = async (event) => {
    // run only once
    if (!self.initialized) {
        self.initialized = true;
        self.documentUrl = event.data.documentUrl;
        self.micropipIncludePre = event.data.micropipIncludePre;
        self.pythonModuleName = event.data.pythonModuleName;
        await self.initPyodide();
    } else {
        // message
        const sendFn = flet_js.send || flet_js.jsSend;
        if (!sendFn) {
            console.error("No send function on flet_js", Object.keys(flet_js));
            return;
        }
        sendFn(event.data);
    }
};