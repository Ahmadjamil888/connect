const vscode = require("vscode");
const fs = require("fs");
const path = require("path");

function writeOpenFiles(context) {
  const filePath = path.join(context.extensionPath, "open_files.json");
  const files = vscode.workspace.textDocuments.map((doc) => doc.uri.fsPath);
  fs.writeFileSync(filePath, JSON.stringify(files, null, 2), "utf8");
}

function activate(context) {
  writeOpenFiles(context);
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(() => writeOpenFiles(context)),
    vscode.workspace.onDidCloseTextDocument(() => writeOpenFiles(context)),
    vscode.commands.registerCommand("imos.openDashboard", () => {
      vscode.env.openExternal(vscode.Uri.parse("http://localhost:8765/imos"));
    })
  );
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
