
https://github.com/Aphranda/RNX_Demo.git

```
RNX_Demo
├─ 📁.idea
├─ 📁.vscode
├─ 📁build
├─ 📁calibrations
│  ├─ 📁archive
│  │  └─ 📄RNX_Cal_DUAL_RefPwr-10.0_-5.0dBm_8.0to40.0GHz_stepFreqList_20250728_094434Z.csv
│  └─ 📁backup
│     ├─ 📄RNX_Cal_PHI_RefPwr-10.0dBm_18.0to26.5GHz_step0.1_20250728_092813Z.csv
│     ├─ 📄RNX_Cal_PHI_RefPwr-10.0dBm_8.0to12.0GHz_step0.1_20250728_092346Z.csv
│     ├─ 📄RNX_Cal_PHI_RefPwr-5.0dBm_12.0to18.0GHz_step0.1_20250728_092123Z.csv
│     ├─ 📄RNX_Cal_PHI_RefPwr-5.0dBm_26.5to40.0GHz_step0.1_20250728_093519Z.csv
│     ├─ 📄RNX_Cal_THETA_RefPwr-10.0dBm_18.0to26.5GHz_step0.1_20250728_094316Z.csv
│     ├─ 📄RNX_Cal_THETA_RefPwr-10.0dBm_8.0to12.0GHz_step0.1_20250728_091457Z.csv
│     ├─ 📄RNX_Cal_THETA_RefPwr-5.0dBm_12.0to18.0GHz_step0.1_20250728_091812Z.csv
│     └─ 📄RNX_Cal_THETA_RefPwr-5.0dBm_26.5to40.0GHz_step0.1_20250728_093939Z.csv
├─ 📁dist
├─ 📁docs
│  ├─ 📄12_18GHZ.csv
│  ├─ 📄18_26.5GHZ.csv
│  ├─ 📄26.5_40GHZ.csv
│  ├─ 📄8_12GHZ.csv
│  ├─ 📄NRPxxSN_UserManual_en_25.pdf
│  ├─ 📄RNX_使用说明文档.md
│  ├─ 📄RNX量子天线测试系统指令表.md
│  ├─ 📄RNX量子天线测试系统指令表.pdf
│  ├─ 📄RNX量子天线测试系统链路图.png
│  ├─ 📄WD-25045 PLASG-T8G40G 信号发生器 软件编程手册(1).pdf
│  ├─ 📄英联标准增益18-40GHz.csv
│  ├─ 📄英联标准增益2-18GHz.csv
│  ├─ 📄软件使用说明.prn
│  ├─ 📄通测暗室测试频点.csv
│  └─ 📄频率分配.png
├─ 📁logs
├─ 📁package
│  └─ 📄requirements.txt
├─ 📁scripts
│  └─ 📄Doicon.py
├─ 📁src
│  ├─ 📁app
│  │  ├─ 📁controllers
│  │  │  ├─ 📁__pycache__
│  │  │  └─ 📄CalibrationFileManager.py
│  │  ├─ 📁core
│  │  │  ├─ 📁exceptions
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄base.py
│  │  │  │  ├─ 📄calibration.py
│  │  │  │  ├─ 📄instrument.py
│  │  │  │  ├─ 📄scpi.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄error_handlers.py
│  │  │  ├─ 📄message_bus.py
│  │  │  ├─ 📄scpi_commands.py
│  │  │  ├─ 📄tcp_client.py
│  │  │  └─ 📄threads.py
│  │  ├─ 📁dialogs
│  │  │  └─ 📄__init__.py
│  │  ├─ 📁instruments
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄factory.py
│  │  │  ├─ 📄interfaces.py
│  │  │  ├─ 📄nrp50s.py
│  │  │  └─ 📄plasg_signal_source.py
│  │  ├─ 📁models
│  │  │  └─ 📄__init__.py
│  │  ├─ 📁threads
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄CalibrationThread.py
│  │  │  └─ 📄StatusQueryThread.py
│  │  ├─ 📁utils
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄ProcessManager.py
│  │  │  └─ 📄SignalUnitConverter.py
│  │  ├─ 📁widgets
│  │  │  ├─ 📁CalibrationPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄CalibrationPanel.py
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  └─ 📄View.py
│  │  │  ├─ 📁LogWidget
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄LogWidget.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁MotionControl
│  │  │  ├─ 📁PlotWdiget
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄PlotWidget.py
│  │  │  │  └─ 📄View.py
│  │  │  ├─ 📁SignalSourceControl
│  │  │  ├─ 📁StatusPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄StatusPanel.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄AutoFontSizeComboBox.py
│  │  │  ├─ 📄AutoFontSizeLabel.py
│  │  │  ├─ 📄factory.py
│  │  │  └─ 📄SimpleLinkDiagram.py
│  │  ├─ 📁__pycache__
│  │  └─ 📄main_window.py
│  ├─ 📁build
│  ├─ 📁calibrations
│  │  ├─ 📁archive
│  │  │  └─ 📄RNX_Cal_综合文件.csv
│  │  └─ 📁backup
│  ├─ 📁debug
│  │  ├─ 📄cal_gain.py
│  │  ├─ 📄debug_calibration_panel.py
│  │  ├─ 📄RNX_Cal_DualPol_8.0to40.0GHz_stepNONE_20250720_124420Z.csv
│  │  ├─ 📄RNX_Demo_TEST.py
│  │  ├─ 📄test.py
│  │  ├─ 📄test_mian.py
│  │  ├─ 📄英联标准增益18-40GHz.csv
│  │  └─ 📄英联标准增益2-18GHz.csv
│  ├─ 📁dist
│  ├─ 📁docs
│  │  ├─ 📄RNX_使用说明文档.pdf
│  │  └─ 📄RNX量子天线测试系统指令表.pdf
│  ├─ 📁resources
│  │  ├─ 📁icons
│  │  │  ├─ 📄icon_calibration.png
│  │  │  ├─ 📄icon_export.png
│  │  │  ├─ 📄icon_help.png
│  │  │  ├─ 📄icon_import.png
│  │  │  ├─ 📄icon_init.png
│  │  │  ├─ 📄icon_plot.png
│  │  │  ├─ 📄icon_RNX_01.ico
│  │  │  └─ 📄icon_settings.png
│  │  ├─ 📁styles
│  │  │  ├─ 📄style.css
│  │  │  ├─ 📄style_bule.qss
│  │  │  ├─ 📄style_dark.qss
│  │  │  └─ 📄style_purple.qss
│  │  ├─ 📁ui
│  │  │  ├─ 📁__pycache__
│  │  │  └─ 📄main_window_ui.py
│  │  └─ 📄resources.qrc
│  ├─ 📁test
│  │  ├─ 📁__pycache__
│  │  └─ 📄SignalUnitConverter_test.py
│  ├─ 📁__pycache__
│  └─ 📄mian.py
├─ 📄.gitignore
├─ 📄calibrations.zip
├─ 📄package.json
└─ 📄readme.md
```
