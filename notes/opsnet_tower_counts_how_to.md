# Getting the FAA tower counts (OPSNET) to Claude

## 1. Download the report

1. Go to https://aspm.faa.gov/opsnet/sys/Airport.asp (public, no login).
2. Report: **Airport Operations**.
3. Facilities: add **LWM**, **OWD**, **BED**.
4. Dates: pick the option that lists **each day separately** (a date range broken out by day, or pick the days on the calendar).
   Cover **2026-07-18 to 2026-09-30** and **2026-03-01 to 2026-03-31**. A whole year is fine too.
5. Run the report. On the results page use the **Excel / export** link to download the file.

The columns needed are the itinerant and local counts, in particular general aviation itinerant and civil local. If the export has every column, that is fine.

## 2. Send it, whichever is easiest

- **Google Drive**: upload the file to your Drive and tell Claude its name. Drive is connected to the session, so Claude can pull it onto the server.
- **Paste**: open the file, select the whole table, paste it into a chat message. A few hundred rows is fine.
- **scp** (if you have SSH to the server):

```bash
scp ~/Downloads/<file name>.xlsx ml-sandbox:/home/dev/wind-limits/reference/opsnet/
```
