# Interactive impact visual

## Run locally

From the `nyc-mobility-operations-portfolio` directory:

```bash
python3 -m http.server 8793
```

Open:

```text
http://localhost:8793/impact-visual/
```

## Story shown

• 3,724,889 source records.

• 194,928 zone-hour metrics.

• 8,423 first-pass alerts.

• 436 final investigation prompts.

• Three interactive operating cases.

• Official NYC TLC taxi-zone map.

• Measured system impact versus business impact awaiting a fleet trial.

• A proposed real-world product path naming the economic buyer, daily users, delivery team, 30-day pilot measures, and ship / stop rule.

The page uses local HTML, CSS, SVG, and JavaScript. It has no external runtime dependency.

## Use the report

1. Select New Year’s event, LaGuardia storm, or post-storm recovery.
2. Hover or focus a highlighted taxi zone.
3. Follow the signal, supply, demand, decision, and impact flow.
4. Treat every action as a human-approved test.

## Test business impact

1. Select five alert-informed test zones.
2. Select five comparable control zones.
3. Change one staging, dispatch, or ETA decision in test zones.
4. Compare trips per driver-hour, revenue per online hour, empty miles, and pickup delay.

## Map source

Official NYC Taxi and Limousine Commission taxi-zone shapefile, downloaded August 23, 2026. The source archive reports a February 19, 2026 modification date.

Source archive: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip

The local map converts the official EPSG:2263 shapefile to WGS84 GeoJSON. It preserves all 263 unique TLC `LocationID` values. No zone geometry was inferred or repaired.

Source ZIP SHA-256: `f6d711917bb4340f8f644d5366c51665489eb2d426dd1a4a55677721ae5adf17`

Local GeoJSON SHA-256: `deb8df09d0e165a748bd419163308cf2780da5d1b38465dfb524fc852a5ccf3c`
