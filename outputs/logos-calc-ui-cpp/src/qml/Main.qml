import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""

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

        Item { Layout.fillHeight: true }
    }
}
