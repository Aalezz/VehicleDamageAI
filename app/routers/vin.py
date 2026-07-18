"""VIN decoder — free NHTSA vPIC API (no key required).

Decodes any 17-character VIN to manufacturer, model, year, engine,
transmission and body specs. Coverage is strongest for vehicles sold in
North America; many global VINs decode partially.
"""
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/vin", tags=["vin"])

NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"

FIELDS = {
    "Make": "make", "Model": "model", "ModelYear": "year", "Trim": "trim",
    "BodyClass": "body", "EngineCylinders": "engine_cylinders",
    "DisplacementL": "engine_liters", "FuelTypePrimary": "fuel",
    "TransmissionStyle": "transmission", "DriveType": "drive",
    "PlantCountry": "made_in", "VehicleType": "vehicle_type",
}


@router.get("/{vin}")
async def decode_vin(vin: str):
    vin = vin.strip().upper()
    if len(vin) != 17:
        raise HTTPException(400, "A VIN must be exactly 17 characters.")
    if any(c in "IOQ" for c in vin):
        raise HTTPException(400, "Invalid VIN: letters I, O and Q are never used in VINs.")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(NHTSA_URL.format(vin=vin))
            r.raise_for_status()
            data = r.json()["Results"][0]
    except httpx.HTTPError:
        raise HTTPException(502, "VIN decoding service unavailable. Try again shortly.")

    out = {"vin": vin}
    for src, dst in FIELDS.items():
        val = (data.get(src) or "").strip()
        if val and val.lower() not in ("not applicable", ""):
            out[dst] = val

    if "make" not in out:
        raise HTTPException(404, "Could not decode this VIN. Check for typos, or enter vehicle details manually.")
    out["error_notes"] = (data.get("ErrorText") or "").split(";")[0].replace("0 - VIN decoded clean.", "").strip()
    return out
