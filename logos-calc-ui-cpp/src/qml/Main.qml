import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""

    function callCalc(method, args) {
        root.result = "..."
        root.errorText = ""
        logos.callModuleAsync("calc_ui_cpp", method, args, function(r) {
            root.result = r
        })
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
                onClicked: root.callCalc("add", [parseInt(inputA.text), parseInt(inputB.text)])
            }

            Button {
                text: "Multiply"
                onClicked: root.callCalc("multiply", [parseInt(inputA.text), parseInt(inputB.text)])
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
                onClicked: root.callCalc("factorial", [parseInt(inputN.text)])
            }

            Button {
                text: "Fibonacci"
                onClicked: root.callCalc("fibonacci", [parseInt(inputN.text)])
            }

            Button {
                text: "libcalc version"
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
