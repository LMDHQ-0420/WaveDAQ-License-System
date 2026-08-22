# WaveDAQ Features and User Guide

WaveDAQ is a desktop data-acquisition and waveform-analysis application for multi-channel sensor experiments. It supports 8-channel UDP data reception, real-time waveform display, record management, threshold filtering, peak and valley detection, CSV import and export, and customizable display settings. This guide describes the main features, common workflows, data formats, and troubleshooting steps.

> Images in this document use reserved files in the `assets/` directory. Add the screenshots using the filenames listed in the Chinese guide or at the end of this document.

## 1. Interface overview

<p align="center"><img src="assets/WaveDAQ-main.png" width="66%" alt="WaveDAQ main interface"/></p>

The main window is titled “WaveDAQ”. The left side contains acquisition controls, channel selection, and settings. The right side contains the raw waveform plot, the filtered waveform plot, and the overview plot. Up to 20 records can be kept during one program session. Records are held in memory and are not automatically restored after the application closes.

| Area | Function |
|---|---|
| Start and Stop | Start or stop one acquisition |
| Record list | View, inspect, recollect, and export records |
| Channel 1–8 | Show or hide an individual channel |
| Enable peak/valley detection | Show or hide real-time peak and valley markers |
| Default Settings | Configure export, channel display, appearance, and the built-in guide |
| Filter Settings | Configure per-channel noise thresholds and adaptive filtering |
| Reset | Restore automatic following and the default view range |
| Import | Create a record from a CSV file |
| Clear | Delete all records in the current session |
| Raw waveform plot | Display the original 8-channel data |
| Filtered waveform plot | Display the threshold-filtered result |
| Overview plot | Show the complete range and locate the main view with the yellow region |

## 2. Basic acquisition workflow

### 2.1 Start an acquisition

1. Make sure the sensor or UDP data source is running.
2. Open WaveDAQ and confirm that waveforms are arriving.
3. Select the channels that should be visible.
4. Enable peak and valley detection if required.
5. Click **▶ Start**.
6. The status line shows the record currently being collected.

The receiver continuously accepts valid UDP frames. Frames first enter the live buffer and are then rendered by the user interface. Downsampling used for drawing does not discard the original samples.

### 2.2 Stop an acquisition

Click **■ Stop**. WaveDAQ flushes the remaining buffer into one record and adds it to the record list. Records are named “数据1”, “数据2”, and so on, and show the acquisition start time.

The session can contain at most 20 records. When the limit is reached, clear old records or use **Recollect** to replace an existing record.

### 2.3 View a record

Each record provides three actions:

- **View**: show the record in the main plots;
- **Details**: show start time, end time, duration, and sample count;
- **Export**: choose channels and export a CSV file.

During playback, the main plot can be panned and zoomed. The overview region can be dragged to locate a range quickly. Click **Reset** or double-click the main plot to restore the automatic view.

### 2.4 Recollect a record

Open a record’s **Details** dialog and click **Recollect** to collect new data and overwrite that record. The application asks for confirmation first. The record name remains unchanged while its data, time, and detection state are replaced.

## 3. Waveform display and navigation

<p align="center"><img src="assets/WaveDAQ-waveform.png" width="66%" alt="WaveDAQ waveform display"/></p>

### 3.1 Raw waveform plot

The raw plot shows all eight channels using independent colors. Channel checkboxes control visibility only; they do not delete data and do not restrict later exports.

The main plot uses approximately 2,000 drawing points for a view. When the data range is large, the current view is downsampled to reduce drawing cost. The record itself keeps the complete sample sequence.

### 3.2 Overview plot and region

The overview plot shows the complete record. The yellow region indicates the range displayed in the main plot:

- drag the yellow region to move the main view;
- drag either edge to change the displayed range;
- drag the main plot to pan;
- double-click the main plot or click **Reset** to restore the automatic view.

### 3.3 Individual channel plots

In **Default Settings → Channel Settings**, enable **Show separately** for a channel to add an individual plot for that channel. Individual plots remain synchronized with the main time range.

## 4. Threshold filtering

<p align="center"><img src="assets/WaveDAQ-filter-settings.png" width="66%" alt="WaveDAQ filter settings"/></p>

### 4.1 Filter behavior

Click **Filter Settings** in the lower-left area. Check **Enable threshold filtering** and confirm the dialog. The filtered waveform plot then becomes visible.

Filtering does not modify the raw record. It only affects the filtered plot and **Export filtered result**.

Each channel has a signed lower and upper threshold. The current filter treats the interval between the thresholds as static noise:

```text
lower bound <= sample <= upper bound: set to zero
sample < lower bound or sample > upper bound: preserve
```

Thresholds may be negative and may cross zero. For example, `-0.1` and `0.1` suppress low-amplitude samples in the range `-0.1` to `0.1` while preserving samples outside that range.

### 4.2 Shared thresholds

Check **Use the same threshold for all eight channels** to synchronize the eight lower inputs and the eight upper inputs separately. When this option is enabled, the largest current lower value is applied to every lower input and the largest current upper value is applied to every upper input.

Uncheck it to return to independent per-channel values.

### 4.3 Adaptive filtering

<p align="center"><img src="assets/WaveDAQ-adaptive-filter.png" width="66%" alt="WaveDAQ adaptive filtering"/></p>

Adaptive filtering estimates thresholds from the current static sensor noise. It does not modify raw data and only generates suggested bounds.

1. Stop the current acquisition.
2. Open **Filter Settings**.
3. Click the small **Adaptive Filtering** button at the bottom of the dialog.
4. Connect the sensor and keep the sensor and object still.
5. Click **Start Calibration**.
6. Keep still while the application samples for five seconds.
7. The bounds for all eight channels are filled automatically.
8. Threshold filtering is checked automatically, but the outer dialog is not confirmed automatically.
9. Review the values and click **OK** to apply them.

Each channel is processed independently using a robust estimate:

```text
center = median(silent samples)
MAD = median(|sample - center|)
robust standard deviation = 1.4826 × MAD
noise radius = max(99th-percentile deviation, 5 × robust standard deviation)
lower bound = center - noise radius
upper bound = center + noise radius
```

This is less sensitive to slow drift and occasional spikes than directly using the minimum and maximum values. The sensor must remain still during calibration; real motion would enlarge the estimated noise interval.

## 5. Peak and valley detection

<p align="center"><img src="assets/WaveDAQ-peak-valley.png" width="66%" alt="WaveDAQ peak and valley detection"/></p>

### 5.1 Enable or disable detection

The **Enable peak/valley detection** checkbox on the left can be switched during acquisition, after acquisition, and during playback.

The detector identifies local extrema on each channel:

- peak: marker value `1`, shown as a thin red cross;
- valley: marker value `-1`, shown as a thin red cross;
- ordinary sample: marker value `0`.

During live acquisition, the application uses incremental processing and rechecks only a short overlapping tail instead of rescanning all historical samples. The main plot displays the newest 500 markers by default. The number can be changed using the small **Advanced** button in the lower-left corner of the **Default Settings** window. This only changes the number of visible markers; it does not affect stored or exported results.

### 5.2 Playback and export

When a record is being viewed, enabling the main detection checkbox shows its detection result and disabling it hides the red markers.

In a record’s **Export** dialog, check **Export peak/valley detection results** to export all eight channels. Each channel uses two columns:

```text
channel 1, marker 1, channel 2, marker 2, ... , channel 8, marker 8
```

This produces 16 columns. If **Include time (ms)** is enabled under **Default Settings → Export Settings**, the first column is a numeric time column and the output contains 17 columns.

## 6. Import data

<p align="center"><img src="assets/WaveDAQ-import.png" width="66%" alt="WaveDAQ data import"/></p>

Click **Import**, located between **Reset** and **Clear** beside the overview plot, to create a record from a CSV file. The imported record uses the original filename, shows “导入” in the record list, and shows `-` for start and end time in the details dialog. Duration and sample count are calculated automatically.

The import dialog has two options:

- **Contains time column**: the first CSV column is time in milliseconds;
- **Contains peak/valley columns**: every channel has an associated marker column.

The file must be a numeric CSV with the same number of columns on every row. Supported layouts are:

| File type | Columns | Layout |
|---|---:|---|
| Plain 8-channel | 8 | channel 1 through channel 8 |
| With time | 9 | time, channel 1 through channel 8 |
| With markers | 16 | channel 1, marker 1, channel 2, marker 2, through channel 8, marker 8 |
| With time and markers | 17 | time, channel 1, marker 1, through channel 8, marker 8 |

Marker columns may contain only `-1`, `0`, or `1`. Imported marker results are retained and can be viewed by enabling peak/valley detection on the main window.

## 7. Export data

<p align="center"><img src="assets/WaveDAQ-export.png" width="66%" alt="WaveDAQ export settings"/></p>

Click **Export** in a record row to open the export dialog. It provides two actions:

- **Export original**: export the original samples;
- **Export filtered result**: export data after threshold filtering is enabled.

Without marker output, the number of columns equals the selected channel count. Enabling **Include time (ms)** adds one numeric time column at the beginning.

Enabling **Export peak/valley detection results** automatically selects all eight channels and exports 16 signal and marker columns. The dialog displays the current column count:

```text
plain export: selected channel count
plain export + time: selected channel count + 1
marker export: 16 columns
marker export + time: 17 columns
```

Default directory, filename, date suffix, time suffix, and the default time-column option can be configured under **Default Settings → Export Settings**. The output is CSV and can be further analyzed with Excel, Origin, MATLAB, Python, or similar tools.

## 8. Default settings

<p align="center"><img src="assets/WaveDAQ-default-settings.png" width="66%" alt="WaveDAQ default settings"/></p>

Click **Default Settings** in the lower-left area. It contains three tabs:

### 8.1 Channel Settings

- change the color of each channel;
- change the display order;
- enable separate channel plots;
- choose a background color;
- hide the combined waveform plot;
- hide the filtered waveform plot.

### 8.2 Export Settings

- choose the default save directory;
- set the default filename;
- append acquisition date;
- append acquisition time;
- choose whether time in milliseconds is included by default.

Filename templates support `{name}`, `{date}`, and `{time}`. For example:

```text
{name}_{date}_{time}.csv
```

### 8.3 User Guide

The **User Guide** tab contains the built-in Chinese operation guide for quick reference.

### 8.4 Advanced Settings

The small **Advanced** button in the lower-left corner of the Default Settings window controls how many newest peak/valley markers are shown in the main plot. A larger number shows more red markers and may increase drawing work. It does not limit detection or export.

## 9. Records and file lifecycle

Current acquisition records are stored in memory:

- clicking **Stop** adds a record to the current list;
- clicking **Clear** deletes all current records;
- closing the application does not automatically restore the records;
- imported data exists only in the current application session;
- data is written to disk only when the user exports a CSV file.

WaveDAQ does not upload acquisition data. When launched through WaveDAQ-Launcher, license files and product download caches are maintained by the Launcher separately; WaveDAQ’s acquisition records remain managed by the current WaveDAQ process.

## 10. Frequently asked questions

### 10.1 No waveform is displayed

Check that the sensor or UDP source is running, that it is sending to the computer running WaveDAQ, that port `8080` is available, and that **Start** has been clicked. For a local test, run `test_udp_sender.py`.

### 10.2 The waveform is intermittent or grows slowly

Check UDP network stability and confirm that the sender continuously sends complete frames. Invalid or incomplete frames are discarded intentionally.

### 10.3 Real signals are weakened after adaptive filtering

Repeat the five-second silent calibration and make sure there is no movement or impact during calibration. You can also widen the thresholds manually or check whether shared thresholds were enabled accidentally.

### 10.4 Too many markers or slow rendering

Open **Default Settings**, click **Advanced** in the lower-left corner, and reduce the number of visible markers. This only reduces red markers on screen and does not delete detection results.

### 10.5 CSV import fails

Make sure the file is a numeric CSV with consistent row lengths, and select import options that match its column count. Plain 8-channel files have 8 columns; time adds one column; marker output requires 16 or 17 columns.

### 10.6 Export filtered result is disabled

Enable threshold filtering in **Filter Settings** and confirm the dialog. Exporting a filtered result does not change the original record.

### 10.7 How can I obtain WaveDAQ?

WaveDAQ is authorized, downloaded, and launched through WaveDAQ-Launcher. Verification-system packages are available from [GitHub Releases](https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases). For authorization or product support, contact [sunyuxiang25@mails.ucas.edu.cn](mailto:sunyuxiang25@mails.ucas.edu.cn).

---

Coding by [sunyuxiang25@mails.ucas.edu.cn](mailto:sunyuxiang25@mails.ucas.edu.cn)
