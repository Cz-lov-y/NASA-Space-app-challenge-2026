import * as THREE from 'three';
import { GeoCoordinate } from '../types/globe';

/**
 * Converts Geographic Latitude and Longitude to Cartesian 3D coordinates on a Sphere of radius R.
 * In Three.js SphereGeometry:
 * - Y is North (+90 deg) / South (-90 deg)
 * - Texture 0 deg longitude (Prime Meridian) is aligned with +Z axis
 */
export function latLngToVector3(lat: number, lng: number, radius: number = 1.0): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  // Three.js UV mapping places Greenwich (0 lon) at +Z when facing the globe
  const theta = (lng + 180) * (Math.PI / 180);

  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const y = radius * Math.cos(phi);
  const z = radius * Math.sin(phi) * Math.sin(theta);

  return new THREE.Vector3(x, y, z);
}

/**
 * Converts a 3D local point on the Earth sphere back to Latitude and Longitude.
 * Must be in the Earth's local coordinate space (after mesh.worldToLocal).
 */
export function vector3ToLatLng(localVector: THREE.Vector3): GeoCoordinate {
  const normalized = localVector.clone().normalize();

  // Latitude: -90 to +90
  const lat = Math.asin(normalized.y) * (180 / Math.PI);

  // Longitude: -180 to +180
  // Derived from: x = -sin(phi)*cos(theta), z = sin(phi)*sin(theta)
  // theta = atan2(z, -x) = (lng + 180) * deg2rad
  let theta = Math.atan2(normalized.z, -normalized.x); // radians in [-PI, PI]
  if (theta < 0) theta += 2 * Math.PI; // [0, 2*PI]

  let lng = (theta * 180) / Math.PI - 180;
  // Normalize to [-180, 180]
  if (lng > 180) lng -= 360;
  if (lng < -180) lng += 360;

  return {
    lat: Number(lat.toFixed(4)),
    lng: Number(lng.toFixed(4)),
  };
}

/**
 * Format latitude and longitude with N/S and E/W notation
 */
export function formatCoordinates(lat: number, lng: number): string {
  const latDir = lat >= 0 ? 'N' : 'S';
  const lngDir = lng >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lng).toFixed(4)}° ${lngDir}`;
}
