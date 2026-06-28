import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""

    // Last payload from the backend's `computed` SIGNAL (see Connections below).
    property string lastSignal: "(none)"

    // Typed replica of the backend running in ui-host (generated from calc_ui_cpp.rep).
    readonly property var backend: logos.module("calc_ui_cpp")

    // The ui-host backend connects asynchronously, so the replica isn't
    // immediately usable. Track readiness reactively: isViewModuleReady()
    // is a Q_INVOKABLE (not a property), so we re-check it on the
    // onViewModuleReadyChanged signal and once at startup — never via a
    // plain property binding, which would not re-evaluate.
    property bool ready: false

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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Text {
            text: "Logos Calculator (C++ backend)"
            font.pixelSize: 20
            color: "#ffffff"
            Layout.alignment: Qt.AlignHCenter
        }

        // Reactive backend-connection indicator.
        Text {
            text: root.ready ? "Connected" : "Connecting to backend..."
            color: root.ready ? "#56d364" : "#f0883e"
            font.pixelSize: 12
            Layout.alignment: Qt.AlignHCenter
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField {
                id: inputA
                placeholderText: "a"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }

            TextField {
                id: inputB
                placeholderText: "b"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }

            Button {
                text: "Add"
                enabled: root.ready
                onClicked: root.callCalc("add", [parseInt(inputA.text) || 0, parseInt(inputB.text) || 0])
            }

            Button {
                text: "Multiply"
                enabled: root.ready
                onClicked: root.callCalc("multiply", [parseInt(inputA.text) || 0, parseInt(inputB.text) || 0])
            }
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField {
                id: inputN
                placeholderText: "n"
                Layout.preferredWidth: 80
                validator: IntValidator { bottom: 0 }
            }

            Button {
                text: "Factorial"
                enabled: root.ready
                onClicked: root.callCalc("factorial", [parseInt(inputN.text) || 0])
            }

            Button {
                text: "Fibonacci"
                enabled: root.ready
                onClicked: root.callCalc("fibonacci", [parseInt(inputN.text) || 0])
            }

            Button {
                text: "libcalc version"
                enabled: root.ready
                onClicked: root.callCalc("libVersion", [])
            }

            Button {
                // Fires the event path: asks calc_module to emit
                // versionReady. No logos.watch() — the result comes
                // back through the versionEvent PROP, not a return value.
                text: "Announce version (event)"
                enabled: root.ready
                onClicked: root.backend.announceVersion()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: root.errorText.length > 0 ? "#3d1a1a" : "#1a2d1a"
            radius: 8

            Text {
                anchors.centerIn: parent
                text: root.errorText.length > 0 ? root.errorText
                        : (root.result.length > 0 ? root.result : "Enter values and press a button")
                color: root.errorText.length > 0 ? "#f85149" : "#56d364"
                font.pixelSize: 15
            }
        }

        // Slot-driven PROP: bumped by the backend's record() after each
        // calculation. A plain property read — auto-syncs, no polling.
        Text {
            text: "Computations: " + ((root.ready && root.backend) ? root.backend.computeCount : 0)
            color: "#cdd6f4"
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
        }

        // SIGNAL payload, captured by the Connections block above.
        Text {
            text: "Last op (signal): " + root.lastSignal
            color: "#94e2d5"
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
        }

        // READWRITE PROP: the memory register. The label *reads*
        // backend.memory; the buttons *write* it. A write round-trips
        // QML → replica → backend source → back to every replica, so the
        // label updates once the new value syncs home.
        RowLayout {
            spacing: 12
            Layout.alignment: Qt.AlignHCenter

            Text {
                text: "Memory: " + ((root.ready && root.backend) ? root.backend.memory : 0)
                color: "#cdd6f4"
                font.pixelSize: 14
            }

            Button {
                text: "Store (MS)"
                enabled: root.ready
                onClicked: root.backend.memory = parseInt(root.result) || 0
            }

            Button {
                text: "Clear (MC)"
                enabled: root.ready
                onClicked: root.backend.memory = 0
            }
        }

        // Event-fed label: the versionEvent PROP auto-syncs from the
        // backend's typed versionReady subscription. No polling — it
        // updates the moment calc_module emits.
        Text {
            readonly property string ev: (root.ready && root.backend) ? root.backend.versionEvent : ""
            text: "Version event: " + (ev.length > 0 ? ev : "(none yet)")
            color: "#f9e2af"
            font.pixelSize: 15
            Layout.alignment: Qt.AlignHCenter
        }

        Item { Layout.fillHeight: true }
    }
}
