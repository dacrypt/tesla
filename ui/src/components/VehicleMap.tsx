import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle, CircleMarker, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// Fix Leaflet default marker icon in bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

export interface GeofenceOverlay {
  name: string;
  lat: number;
  lon: number;
  radius_km: number;
}

interface VehicleMapProps {
  latitude: number;
  longitude: number;
  label?: string;
  height?: string;
  geofences?: GeofenceOverlay[];
  heatPoints?: { lat: number; lon: number }[];
  trackPoints?: [number, number][];
}

function RecenterMap({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  const prevRef = useRef({ lat, lng });
  useEffect(() => {
    if (prevRef.current.lat !== lat || prevRef.current.lng !== lng) {
      map.setView([lat, lng], map.getZoom(), { animate: true });
      prevRef.current = { lat, lng };
    }
  }, [lat, lng, map]);
  return null;
}

export default function VehicleMap({ latitude, longitude, label, height = '400px', geofences, heatPoints, trackPoints }: VehicleMapProps) {
  const showMarker = latitude !== 0 || longitude !== 0;
  const center: [number, number] = trackPoints && trackPoints.length > 0
    ? trackPoints[Math.floor(trackPoints.length / 2)]
    : heatPoints && heatPoints.length > 0 && !showMarker
      ? [heatPoints[Math.floor(heatPoints.length / 2)].lat, heatPoints[Math.floor(heatPoints.length / 2)].lon]
      : [latitude, longitude];
  const zoom = trackPoints && trackPoints.length > 0 ? 13 : heatPoints && heatPoints.length > 0 && !showMarker ? 11 : 15;

  return (
    <div style={{ height, width: '100%', borderRadius: 12, overflow: 'hidden' }}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        {showMarker && (
          <Marker position={[latitude, longitude]}>
            {label && <Popup>{label}</Popup>}
          </Marker>
        )}
        {geofences?.map((g) => (
          <Circle
            key={g.name}
            center={[g.lat, g.lon]}
            radius={g.radius_km * 1000}
            pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 0.15 }}
          >
            <Popup>{g.name} ({g.radius_km} km)</Popup>
          </Circle>
        ))}
        {heatPoints?.map((p, i) => (
          <CircleMarker
            key={i}
            center={[p.lat, p.lon]}
            radius={2}
            pathOptions={{ color: '#10b981', fillOpacity: 0.6, stroke: false }}
          />
        ))}
        {trackPoints && trackPoints.length > 0 && (
          <Polyline
            positions={trackPoints}
            pathOptions={{ color: '#10b981', weight: 3, opacity: 0.8 }}
          />
        )}
        {!heatPoints && !trackPoints && <RecenterMap lat={latitude} lng={longitude} />}
      </MapContainer>
    </div>
  );
}
