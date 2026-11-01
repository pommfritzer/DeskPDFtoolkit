# Design decisions

## 0.2 visual direction

The current interface uses one full-width top navigation band, 30% shorter than the original one-sixth-height band. Branding, search, the active tool name and Settings live in a single row. Category buttons have been removed. Clicking the DeskPDF brand returns to all tools. The main gallery uses large vector tool icons with short labels. The old sidebar and large promotional headline have been removed.

The background is a locally drawn dark green gradient with slowly moving translucent ribbons and a fixed grey dot grid. It uses Qt painting and a bounded timer, without video assets or network resources. Painting pauses while minimized; Settings can pause animation entirely. Dark translucent surfaces and light text preserve contrast over the moving background.

The combined merge grid starts with 260-pixel page previews. A slider adjusts them from 140 to 650 pixels, with debounced rendering at the chosen resolution. Resizing updates icons in place so selection, source identity and output order survive. The source list stays compact while the page workspace occupies the larger column.

The sections below record the original interaction and technology decisions; the visual direction above supersedes the original paper palette and sidebar.

## Product

Make frequent PDF operations short and predictable. The tool library is the entry point; each tool has one workbench with the same file → settings → save sequence. No account, subscription, marketing banner, upload step, or dashboard statistics.

## Visual hierarchy

The page title names the job. A brief sentence defines its scope. The input list and settings occupy the left column; the original-document preview anchors the right. A single dark green save button is the primary action. Secondary controls are outlined. Labels remain visible rather than relying on placeholders.

The library uses an even three-column grid, grouped navigation and search. The muted paper background and green accents establish a calm utility. The application icon combines a folded sheet and a check mark; the same artwork is supplied at Windows icon sizes and as an editable SVG.

## Interaction

- Opening files does not modify them. Every completed operation writes a new output path.
- Output dialogs suggest a descriptive suffix beside the original. The user controls the location.
- Files remain on hand when switching tools, allowing another operation without reopening them. Tools that accept one input explicitly reject multiple files.
- Merge and image input support drag ordering. Page expressions support exact sequence control.
- Previews show originals and say so explicitly. This release does not pretend to provide live output previews.
- Opening password and new password are separate fields. Passwords are masked and not persisted.
- Progress is indeterminate because MuPDF operations do not expose a reliable cross-tool progress count.
- Jobs run in a background thread. Controls are locked until the job completes, and closing waits for the active job. Cancellation is not offered because MuPDF cannot safely interrupt every operation mid-call.
- Errors appear next to the save action, preserving settings for correction. Save failure never replaces an existing destination.
- Keyboard shortcuts: Ctrl+O opens files, Ctrl+K focuses tool search. Standard widgets provide keyboard navigation, focus indicators and accessible labels.

## Technology

Qt supplies a native desktop event loop, accessibility, dialogs, clipboard and high-DPI support without a local web server or browser runtime. Python keeps the processing paths straightforward to audit. The engine can be tested without creating a window.

MuPDF supplies a mature renderer and manipulation engine. AGPL licensing suits an entirely open-source app; any distributor must honor the bundled dependency licenses. Office and OCR integrations use isolated temporary workspaces and explicit executable arguments, with no shell interpolation or document uploads.

PyInstaller bundles a directory rather than a self-extracting executable, avoiding repeated extraction on startup. Inno Setup wraps that directory in one installer with per-user shortcuts and optional removable Explorer verbs. Registry integration deliberately uses the classic Explorer menu rather than claiming unsupported Windows 11 modern-menu integration.

## Release follow-ups

Code signing, clean-machine Windows 10/11 testing, screen-reader testing, translated labels, live output previews, large-file resource budgeting, multi-file Explorer handoff, and richer geometric editing should be reviewed before a stable 1.0 release. LibreOffice conversion was verified locally with a generated Word document. OCR still needs an installed-Tesseract end-to-end test; its missing-dependency path was verified.
