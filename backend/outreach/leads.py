"""Find contractor businesses with the Google Places API (New) Text Search."""
from __future__ import annotations

from typing import Any

import requests

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.businessStatus",
        "nextPageToken",
    ]
)

TRADE_QUERIES = {
    "ac_restoration": "AC repair and HVAC restoration contractor",
    "roofing": "roofing contractor",
    "general_contractor": "general contractor",
    "insulation": "insulation contractor",
}


class PlacesError(RuntimeError):
    pass


def search_places(api_key: str, trade: str, city: str, max_results: int = 20) -> list[dict[str, Any]]:
    if not api_key:
        raise PlacesError("GOOGLE_PLACES_API_KEY is not set")
    query = f"{TRADE_QUERIES.get(trade, trade)} in {city}"
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK, "Content-Type": "application/json"}
    results: list[dict[str, Any]] = []
    page_token: str | None = None

    while len(results) < max_results:
        body: dict[str, Any] = {"textQuery": query, "pageSize": min(20, max_results - len(results))}
        if page_token:
            body["pageToken"] = page_token
        resp = requests.post(PLACES_URL, json=body, headers=headers, timeout=20)
        if resp.status_code != 200:
            raise PlacesError(f"Places API {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        for place in data.get("places", []):
            if place.get("businessStatus") not in (None, "OPERATIONAL"):
                continue
            results.append(
                {
                    "trade": trade,
                    "name": place.get("displayName", {}).get("text", "Unknown"),
                    "phone": place.get("nationalPhoneNumber"),
                    "website": place.get("websiteUri"),
                    "address": place.get("formattedAddress"),
                    "city": city,
                    "rating": place.get("rating"),
                    "source": "google_places",
                    "place_id": place.get("id"),
                }
            )
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results[:max_results]
