import argparse
import csv
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


API_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.types",
        "nextPageToken",
    ]
)


def search_places(api_key, query, max_pages=3):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    places = []
    page_token = None

    for page in range(max_pages):
        body = {
            "textQuery": query,
            "pageSize": 20,
        }

        if page_token:
            body["pageToken"] = page_token

        response = requests.post(
            API_URL,
            headers=headers,
            json=body,
            timeout=30,
        )

        if not response.ok:
            try:
                error = response.json()
            except ValueError:
                error = response.text

            raise RuntimeError(
                f"Google Places API error ({response.status_code}): {error}"
            )

        data = response.json()
        places.extend(data.get("places", []))

        page_token = data.get("nextPageToken")

        if not page_token:
            break

        # Give the next page token a moment to become valid.
        time.sleep(2)

    return places


def clean_places(places):
    unique = {}

    for place in places:
        place_id = place.get("id")

        if not place_id:
            continue

        display_name = place.get("displayName", {})
        name = display_name.get("text", "")

        unique[place_id] = {
            "business_name": name,
            "address": place.get("formattedAddress", ""),
            "phone": (
                place.get("nationalPhoneNumber")
                or place.get("internationalPhoneNumber")
                or ""
            ),
            "website": place.get("websiteUri", ""),
            "google_maps_url": place.get("googleMapsUri", ""),
            "place_id": place_id,
            "types": ", ".join(place.get("types", [])),
        }

    return list(unique.values())


def save_csv(rows, area, category):
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "leads.csv"

    fieldnames = [
        "business_name",
        "category",
        "area",
        "address",
        "phone",
        "website",
        "google_maps_url",
        "place_id",
        "types",
    ]

    with output_file.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            row["category"] = category
            row["area"] = area
            writer.writerow(row)

    return output_file


def main():
    load_dotenv()

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise SystemExit(
            "ERROR: GOOGLE_MAPS_API_KEY is not set. "
            "Create a local .env file and add your API key."
        )

    parser = argparse.ArgumentParser(
        description="Find business leads using Google Places API."
    )

    parser.add_argument(
        "--area",
        required=True,
        help="Area/city to search",
    )

    parser.add_argument(
        "--category",
        required=True,
        help="Business category to search",
    )

    args = parser.parse_args()

    query = f"{args.category} in {args.area}"

    print(f"Searching: {query}")

    places = search_places(
        api_key=api_key,
        query=query,
        max_pages=3,
    )

    rows = clean_places(places)

    output_file = save_csv(
        rows=rows,
        area=args.area,
        category=args.category,
    )

    print(f"Found {len(rows)} unique businesses.")
    print(f"CSV saved to: {output_file}")


if __name__ == "__main__":
    main()
