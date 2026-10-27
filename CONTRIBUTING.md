# Contributing

rog-lighting is open source under the MIT License, and anyone is welcome to contribute. Bug fixes, support for more laptop models, new tests, documentation and UI improvements are all appreciated.

## Ways to help

- **Report your model.** Open an issue with your laptop model and the output of `rog-lighting status`, and say what worked and what didn't. Even "everything works on my GA403UV" is useful.
- **Fix a bug or add a feature.** Fork the repo, make your change on a branch, and open a pull request.
- **Add tests.** Tests live in `tests/`. They check the exact bytes sent to each device, so they run without any ASUS hardware.
- **Add support for a new device.** Include the HID report descriptor (`xxd -p /sys/class/hidraw/hidrawN/device/report_descriptor`) and say where the packet format came from.

## Development

There are no dependencies beyond what Ubuntu ships with: Python 3 and GTK4/libadwaita through `python3-gi`.

```bash
./rog-lighting                     # run from the source tree
python3 -m unittest discover -s tests -v
```

## Ground rules

- Keep it local. Pull requests that add network access, telemetry or analytics won't be merged.
- Don't send untested packets to hardware by default. If you aren't sure about a packet, put it behind an option and say so in the PR.
- Keep the code style consistent with what's there.

By submitting a contribution, you agree that it is licensed under the MIT License.
