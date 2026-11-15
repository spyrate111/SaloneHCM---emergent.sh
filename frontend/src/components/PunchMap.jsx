/**
 * GPS punch map — OpenStreetMap via Leaflet. Green dots = in-zone punches,
 * red = out-of-zone, gray = no GPS fix. Branch geofences render as blue circles.
 */
import { useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Circle, Tooltip } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const FREETOWN = [8.4657, -13.2317];

const dotColor = (p) =>
  p.in_zone === true ? "#0A4A1E" : p.in_zone === false ? "#B03A2E" : "#8A8F96";

export default function PunchMap({ punches = [], branches = [], height = 300 }) {
  const pts = punches.filter((p) => p.lat != null && p.lng != null);
  const branchPts = branches.filter((b) => b.lat != null && b.lng != null);

  const bounds = useMemo(() => {
    const coords = [
      ...pts.map((p) => [p.lat, p.lng]),
      ...branchPts.map((b) => [b.lat, b.lng]),
    ];
    if (coords.length === 0) return null;
    return L.latLngBounds(coords).pad(0.35);
  }, [pts, branchPts]);

  const mapKey = `${pts.length}-${branchPts.length}-${pts[0]?.id || "none"}`;

  return (
    <div className="rounded-xl overflow-hidden border border-[#E2DFD6]" style={{ height }} data-testid="punch-map">
      <MapContainer
        key={mapKey}
        {...(bounds ? { bounds } : { center: FREETOWN, zoom: 13 })}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={false}
        attributionControl={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        {branchPts.map((b) => (
          <Circle
            key={b.id}
            center={[b.lat, b.lng]}
            radius={b.geofence_radius_m || 250}
            pathOptions={{ color: "#0072C6", weight: 1.5, fillColor: "#0072C6", fillOpacity: 0.08 }}
          >
            <Tooltip direction="top">
              <span className="text-xs font-semibold">{b.name}</span>
              <br />
              <span className="text-[10px]">geofence {Math.round(b.geofence_radius_m || 250)}m</span>
            </Tooltip>
          </Circle>
        ))}
        {pts.map((p) => (
          <CircleMarker
            key={p.id}
            center={[p.lat, p.lng]}
            radius={8}
            pathOptions={{ color: "#ffffff", weight: 2, fillColor: dotColor(p), fillOpacity: 0.95 }}
          >
            <Tooltip direction="top">
              <span className="text-xs font-semibold">{p.employee_name}</span>
              <br />
              <span className="text-[10px] uppercase">{p.kind}</span>{" · "}
              <span className="text-[10px]">
                {new Date(p.clocked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
              {p.distance_from_branch_m != null && (
                <>
                  <br />
                  <span className="text-[10px]">
                    {Math.round(p.distance_from_branch_m)}m from {p.branch_name || "branch"}
                    {p.in_zone === false ? " — OUT OF ZONE" : ""}
                  </span>
                </>
              )}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
