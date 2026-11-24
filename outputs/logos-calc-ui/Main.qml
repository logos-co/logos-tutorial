import QtQuick
import QtQuick.Layouts

import Logos.Theme
import Logos.Controls
import Logos.Layouts

Rectangle {
    id: root

    property string result: ""
    property string errorText: ""
    property string versionFromEvent: ""

    // The host sizes the view to the app's area; paint it, as a bare Item
    // would show the host's clear colour.
    color: Theme.palette.background

    // ── Event subscription ────────────────────────────────────
    // Subscribe to "versionReady" events pushed from calc_module.
    Component.onCompleted: {
        if (typeof logos !== "undefined" && logos.onModuleEvent)
            logos.onModuleEvent("calc_module", "versionReady")
    }

    Connections {
        target: typeof logos !== "undefined" ? logos : null
        function onModuleEventReceived(moduleName, eventName, data) {
            if (eventName === "versionReady")
                root.versionFromEvent = data[0]
        }
    }

    // A section's caption.
    component Caption: LogosText {
        Layout.fillWidth: true
        font.pixelSize: Theme.typography.secondaryText
        color: Theme.palette.textSecondary
        wrapMode: Text.Wrap
    }

    LogosScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: Theme.pageMargin(root.width)
        contentWidth: availableWidth

        ColumnLayout {
            width: scroll.availableWidth
            spacing: Theme.spacing.xlarge

            // ── Title ──────────────────────────────────────────────
            LogosPageHeader {
                Layout.fillWidth: true
                title: "Logos Calculator"
                subtitle: "calc_module, called from QML"
            }

            // ── Pattern 1: Direct call (request -> response) ──────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.maximumWidth: Theme.layouts.form.maximumWidth
                spacing: Theme.spacing.medium

                Caption { text: "Direct calls (logos.callModule -> returns result)" }

                // The fields share the width; the buttons wrap onto a new
                // line where they don't fit, as on a phone.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing.medium

                    LogosTextField {
                        id: inputA
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        placeholderText: "a"
                        validator: IntValidator {}
                    }

                    LogosTextField {
                        id: inputB
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        placeholderText: "b"
                        validator: IntValidator {}
                    }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.spacing.medium

                    LogosButton {
                        objectName: "calc_ui.addButton"
                        text: "Add"
                        onClicked: callTwoOp("add", inputA.text, inputB.text)
                    }

                    LogosButton {
                        text: "Multiply"
                        onClicked: callTwoOp("multiply", inputA.text, inputB.text)
                    }
                }

                LogosTextField {
                    id: inputN
                    Layout.fillWidth: true
                    placeholderText: "n"
                    validator: IntValidator { bottom: 0 }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.spacing.medium

                    LogosButton {
                        text: "Factorial"
                        onClicked: callOneOp("factorial", inputN.text)
                    }

                    LogosButton {
                        text: "Fibonacci"
                        onClicked: callOneOp("fibonacci", inputN.text)
                    }

                    LogosButton {
                        text: "libcalc version"
                        onClicked: callModule("libVersion", [])
                    }
                }

                // Direct call result: green, or red with what went wrong.
                LogosNotice {
                    Layout.fillWidth: true
                    severity: root.errorText.length > 0 ? LogosNotice.Error : LogosNotice.Success
                    message: root.errorText.length > 0 ? root.errorText
                             : (root.result.length > 0 ? root.result : "Enter values and press a button")
                }
            }

            // ── Pattern 2: Event-based (fire-and-forget -> event) ─
            ColumnLayout {
                Layout.fillWidth: true
                Layout.maximumWidth: Theme.layouts.form.maximumWidth
                spacing: Theme.spacing.medium

                Caption { text: "Event-based (fire-and-forget call -> result via event)" }

                LogosButton {
                    text: "libcalc version (event)"
                    onClicked: {
                        if (typeof logos !== "undefined" && logos.callModule)
                            logos.callModule("calc_module", "libVersionNotify", [])
                    }
                }

                // Event result
                LogosNotice {
                    Layout.fillWidth: true
                    severity: LogosNotice.Info
                    message: root.versionFromEvent.length > 0
                             ? ("Version (via event): " + root.versionFromEvent)
                             : "Press the event button — result arrives via event"
                }
            }
        }
    }

    // ── Direct call helpers ───────────────────────────────────

    function callModule(method, args) {
        root.errorText = ""
        root.result = ""

        if (typeof logos === "undefined" || !logos.callModule) {
            root.errorText = "Logos bridge not available"
            return
        }

        root.result = String(logos.callModule("calc_module", method, args))
    }

    function callTwoOp(method, a, b) {
        if (a === "" || b === "") { root.errorText = "Enter values for a and b"; return }
        callModule(method, [parseInt(a), parseInt(b)])
    }

    function callOneOp(method, n) {
        if (n === "") { root.errorText = "Enter a value for n"; return }
        callModule(method, [parseInt(n)])
    }
}
