"""Prepare a small Connector fix: reuse a verified paper tab when requested."""
# SPDX-License-Identifier: AGPL-3.0-or-later
# Contains matching context derived from ZotPilot Connector agentAPI.js.
# Copyright (c) 2026 ZotPilot Contributors. See THIRD_PARTY_NOTICES.md.
from pathlib import Path
import argparse

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',required=True)
parser.add_argument('--out',required=True)
args=parser.parse_args()
source=Path(args.source).resolve()
output=Path(args.out).resolve()
if source==output or output.exists():
    raise ValueError('Prepare a new output file; never patch source in place.')
text=source.read_text(encoding="utf-8-sig")
if 'if (command.reuse_existing)' in text and 'closeTabAfterSave' in text:
    anchor='&& current.pathname.replace(/\\/$/, "") === expected.pathname.replace(/\\/$/, "")'
    if '&& current.search === expected.search' not in text:
        if text.count(anchor)!=1:
            raise RuntimeError('Existing reuse patch anchor changed; refuse patch.')
        text=text.replace(anchor,anchor+'\n\t\t\t\t\t\t\t&& current.search === expected.search',1)
    output.write_text(text,encoding='utf-8')
    print('Prepared checked tab-reuse patch; source unchanged.')
    raise SystemExit(0)
anchor="""\tasync function _handleSave(command) {
\t\tconst { request_id, url } = command;
\t\t_busy = true;
\t\tZotero.Connector_Browser.setKeepServiceWorkerAlive(true);
\t\tlet tabId = null;"""
if text.count(anchor)!=1:
    raise RuntimeError("Save-handler anchor changed; refuse patch.")
text=text.replace(anchor,anchor+"\n\t\tlet closeTabAfterSave = true;",1)
anchor="""\t\t\t// 2. Open tab
\t\t\tlet tab = await browser.tabs.create({ url: url, active: false });
\t\t\ttabId = tab.id;"""
replacement="""\t\t\t// Reuse a user-verified paper tab when requested. Leave that tab open.
\t\t\tlet tab = null;
\t\t\tif (command.reuse_existing) {
\t\t\t\tconst expected = new URL(url);
\t\t\t\tconst tabs = await browser.tabs.query({});
\t\t\t\ttab = tabs.find(candidate => {
\t\t\t\t\tif (!candidate.url || candidate.status !== "complete") return false;
\t\t\t\t\ttry {
\t\t\t\t\t\tconst current = new URL(candidate.url);
\t\t\t\t\t\treturn current.origin === expected.origin
\t\t\t\t\t\t\t&& current.pathname.replace(/\\/$/, "") === expected.pathname.replace(/\\/$/, "")
\t\t\t\t\t\t\t&& current.search === expected.search
\t\t\t\t\t\t\t&& !ANTI_BOT_PATTERNS.some(pattern => (candidate.title || "").toLowerCase().includes(pattern));
\t\t\t\t\t} catch (error) { return false; }
\t\t\t\t}) || null;
\t\t\t}
\t\t\tif (tab) {
\t\t\t\tcloseTabAfterSave = false;
\t\t\t\tawait browser.tabs.update(tab.id, { active: true });
\t\t\t} else {
\t\t\t\ttab = await browser.tabs.create({ url: url, active: false });
\t\t\t}
\t\t\ttabId = tab.id;"""
if text.count(anchor)!=1:
    raise RuntimeError("Tab-creation anchor changed; refuse patch.")
text=text.replace(anchor,replacement,1)
anchor="""\t\t\tif (tabId) {
\t\t\t\ttry { await browser.tabs.remove(tabId); } catch (e) {}
\t\t\t\t_pendingSaves.delete(tabId);
\t\t\t}"""
replacement="""\t\t\tif (tabId) {
\t\t\t\tif (closeTabAfterSave) {
\t\t\t\t\ttry { await browser.tabs.remove(tabId); } catch (e) {}
\t\t\t\t}
\t\t\t\t_pendingSaves.delete(tabId);
\t\t\t}"""
if text.count(anchor)!=1:
    raise RuntimeError("Save cleanup anchor changed; refuse patch.")
text=text.replace(anchor,replacement,1)
text=text.replace("extension_version: browser.runtime.getManifest().version,", "extension_version: browser.runtime.getManifest().version + \"+tabreuse\",", 1)
output.write_text(text,encoding="utf-8")
print("Prepared verified-tab reuse patch; original unchanged.")
