import QtQuick
import QtQuick.Layouts

import Logos.Theme
import Logos.Controls
import Logos.Layouts

Rectangle {
    id: root

    property string result: ""
    property string errorText: ""

    // Last payload from the backend's `computed` SIGNAL (see Connections below).
    property string lastSignal: "(none)"

    // Typed replica of the backend module (generated from calc_ui_cpp.rep).
    readonly property var backend: logos.module("calc_ui_cpp")

    // The backend is a separate module and connects asynchronously, so
    // the replica isn't usable at once. Track readiness reactively: isViewModuleReady()
    // is a Q_INVOKABLE (not a property), so we re-check it on the
    // onViewModuleReadyChanged signal and once at startup — never via a
    // plain property binding, which would not re-evaluate.
    property bool ready: false

    // The host sizes the view to the app's area; paint it, as a bare Item
    // would show the host's clear colour.
    color: Theme.palette.background

    Connections {
        target: logos
        function onViewModuleReadyChanged(moduleName, isReady) {
            if (moduleName === "calc_ui_cpp")
                root.ready = isReady && root.backend !== null
        }
    }
    Component.onCompleted: {
        root.ready = root.backend !== null && logos.isViewModuleReady("calc_ui_cpp")
    }

    // SIGNAL from the .rep: the backend emits `computed(op, result)` after
    // each calculation. The typed replica re-emits it, so we catch it with
    // a Connections block — no logos.watch(), no property read. This is the
    // backend → view push path, distinct from the slot return value above.
    Connections {
        target: root.backend
        function onComputed(op, result) {
            root.lastSignal = op + " = " + result
        }
    }

    // logos.watch() delivers the result of a replica slot call via callbacks.
    // No QtRemoteObjects import needed — the bridge handles it.
    function callCalc(method, args) {
        if (!root.ready) {
            root.errorText = "Backend not ready"
            return
        }
        root.errorText = ""
        root.result = "..."
        logos.watch(backend[method].apply(backend, args),
            function(value) { root.result = String(value) },
            function(error) { root.errorText = String(error) }
        )
    }

    // A line of what the backend reports.
    component Readout: LogosText {
        Layout.fillWidth: true
        textFormat: Text.PlainText
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

            // Title, and the reactive backend-connection indicator.
            LogosPageHeader {
                Layout.fillWidth: true
                title: "Logos Calculator (C++ backend)"
                subtitle: root.ready ? "Connected" : "Connecting to backend..."
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.maximumWidth: Theme.layouts.form.maximumWidth
                spacing: Theme.spacing.medium

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
                        objectName: "calc_ui_cpp.addButton"
                        text: "Add"
                        enabled: root.ready
                        onClicked: root.callCalc("add", [parseInt(inputA.text) || 0, parseInt(inputB.text) || 0])
                    }

                    LogosButton {
                        text: "Multiply"
                        enabled: root.ready
                        onClicked: root.callCalc("multiply", [parseInt(inputA.text) || 0, parseInt(inputB.text) || 0])
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
                        enabled: root.ready
                        onClicked: root.callCalc("factorial", [parseInt(inputN.text) || 0])
                    }

                    LogosButton {
                        text: "Fibonacci"
                        enabled: root.ready
                        onClicked: root.callCalc("fibonacci", [parseInt(inputN.text) || 0])
                    }

                    LogosButton {
                        text: "libcalc version"
                        enabled: root.ready
                        onClicked: root.callCalc("libVersion", [])
                    }

                    LogosButton {
                        // Fires the event path: asks calc_module to emit
                        // versionReady. No logos.watch() — the result comes
                        // back through the versionEvent PROP, not a return value.
                        text: "Announce version (event)"
                        enabled: root.ready
                        onClicked: root.backend.announceVersion()
                    }
                }

                // The slot's return value: green, or red with what went wrong.
                LogosNotice {
                    Layout.fillWidth: true
                    severity: root.errorText.length > 0 ? LogosNotice.Error : LogosNotice.Success
                    message: root.errorText.length > 0 ? root.errorText
                             : (root.result.length > 0 ? root.result : "Enter values and press a button")
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.maximumWidth: Theme.layouts.form.maximumWidth
                spacing: Theme.spacing.medium

                // Slot-driven PROP: bumped by the backend's record() after each
                // calculation. A plain property read — auto-syncs, no polling.
                Readout {
                    text: "Computations: " + ((root.ready && root.backend) ? root.backend.computeCount : 0)
                }

                // SIGNAL payload, captured by the Connections block above.
                Readout {
                    text: "Last op (signal): " + root.lastSignal
                }

                // READWRITE PROP: the memory register. The label *reads*
                // backend.memory; the buttons *write* it. A write round-trips
                // QML → replica → backend source → back to every replica, so the
                // label updates once the new value syncs home.
                Readout {
                    text: "Memory: " + ((root.ready && root.backend) ? root.backend.memory : 0)
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.spacing.medium

                    LogosButton {
                        text: "Store (MS)"
                        enabled: root.ready
                        onClicked: root.backend.memory = parseInt(root.result) || 0
                    }

                    LogosButton {
                        text: "Clear (MC)"
                        enabled: root.ready
                        onClicked: root.backend.memory = 0
                    }
                }

                // Event-fed label: the versionEvent PROP auto-syncs from the
                // backend's typed versionReady subscription. No polling — it
                // updates the moment calc_module emits.
                Readout {
                    readonly property string ev: (root.ready && root.backend) ? root.backend.versionEvent : ""
                    text: "Version event: " + (ev.length > 0 ? ev : "(none yet)")
                }
            }
        }
    }
}
