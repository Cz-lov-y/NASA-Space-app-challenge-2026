import React, { useRef } from 'react';
import * as THREE from 'three';
import { useFrame, useLoader, ThreeEvent } from '@react-three/fiber';
import { Atmosphere } from './Atmosphere';
import { LocationPin } from './LocationPin';
import { vector3ToLatLng, latLngToVector3 } from '../../utils/coordinates';
import { GeoCoordinate, SelectedLocation } from '../../types/globe';

interface EarthGlobeProps {
  regions: SelectedLocation[];
  onSelectCoordinate: (coord: GeoCoordinate) => void;
  selectedCoordinate: GeoCoordinate | null;
  isInteracting: boolean;
}

export const EarthGlobe: React.FC<EarthGlobeProps> = ({
  regions,
  onSelectCoordinate,
  selectedCoordinate,
  isInteracting,
}) => {
  const earthGroupRef = useRef<THREE.Group>(null);
  const earthMeshRef = useRef<THREE.Mesh>(null);
  const cloudsRef = useRef<THREE.Mesh>(null);

  // Load authentic NASA Blue Marble textures from public folder
  const [dayMap, normalMap, specularMap, cloudsMap] = useLoader(THREE.TextureLoader, [
    '/textures/earth_day_2048.jpg',
    '/textures/earth_normal_2048.jpg',
    '/textures/earth_specular_2048.jpg',
    '/textures/earth_clouds_1024.png',
  ]);

  // Configure texture parameters
  dayMap.colorSpace = THREE.SRGBColorSpace;
  normalMap.colorSpace = THREE.NoColorSpace;
  specularMap.colorSpace = THREE.NoColorSpace;
  cloudsMap.colorSpace = THREE.SRGBColorSpace;

  // Track interaction pause timer for idle rotation
  const lastInteractionTimeRef = useRef<number>(0);

  // Handle continuous rotation & cloud drift
  useFrame((state, delta) => {
    if (isInteracting) {
      lastInteractionTimeRef.current = state.clock.getElapsedTime();
    }

    // Only rotate if user hasn't interacted for > 1.2 seconds
    const timeSinceInteraction = state.clock.getElapsedTime() - lastInteractionTimeRef.current;
    const shouldRotate = !isInteracting && timeSinceInteraction > 1.2;

    if (earthGroupRef.current && shouldRotate) {
      earthGroupRef.current.rotation.y += delta * 0.04;
    }

    // Clouds drift continuously relative to Earth surface
    if (cloudsRef.current) {
      cloudsRef.current.rotation.y += delta * 0.055;
    }
  });

  // Handle click on the Earth sphere
  const handlePointerDown = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    if (!earthMeshRef.current) return;

    // Convert world intersection point to Earth's local coordinate space
    const localIntersection = earthMeshRef.current.worldToLocal(e.point.clone());
    const geo = vector3ToLatLng(localIntersection);

    onSelectCoordinate(geo);
  };

  return (
    <group ref={earthGroupRef}>
      {/* Main Earth Surface Mesh */}
      <mesh
        ref={earthMeshRef}
        onPointerDown={handlePointerDown}
      >
        <sphereGeometry args={[1, 64, 64]} />
        <meshStandardMaterial
          map={dayMap}
          normalMap={normalMap}
          normalScale={new THREE.Vector2(0.85, 0.85)}
          roughnessMap={specularMap}
          roughness={0.65}
          metalness={0.1}
        />
      </mesh>

      {/* Cloud Layer (Slightly larger radius, semi-transparent) */}
      <mesh ref={cloudsRef} scale={[1.009, 1.009, 1.009]}>
        <sphereGeometry args={[1, 64, 64]} />
        <meshStandardMaterial
          map={cloudsMap}
          transparent
          opacity={0.36}
          blending={THREE.NormalBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Atmospheric Rayleigh Corona Glow */}
      <Atmosphere />

      {regions.filter(r => r.hasObservationalData).map(region => (
        <mesh key={region.id} position={latLngToVector3(region.lat, region.lng, 1.012)}
          onPointerDown={event => { event.stopPropagation(); onSelectCoordinate({lat: region.lat, lng: region.lng}); }}>
          <sphereGeometry args={[0.006, 8, 8]} />
          <meshBasicMaterial color={region.screeningStatus === 'supported_signal' ? '#f59e0b' : region.screeningStatus === 'uncertain_signal' ? '#a78bfa' : '#00e5ff'} />
        </mesh>
      ))}
      {/* Animated Location Pin (attached to the rotating Earth coordinate frame) */}
      {selectedCoordinate && (
        <LocationPin
          lat={selectedCoordinate.lat}
          lng={selectedCoordinate.lng}
          radius={1.0}
        />
      )}
    </group>
  );
};
