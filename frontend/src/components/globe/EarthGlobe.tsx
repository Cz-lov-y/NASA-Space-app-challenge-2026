import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useFrame, useLoader, useThree, ThreeEvent } from '@react-three/fiber';
import { Atmosphere } from './Atmosphere';
import { LocationPin } from './LocationPin';
import { vector3ToLatLng, latLngToVector3 } from '../../utils/coordinates';
import { GeoCoordinate, SelectedLocation } from '../../types/globe';
import { CellOverlay } from './CellOverlay';

interface EarthGlobeProps {
  regions: SelectedLocation[];
  onSelectCoordinate: (coord: GeoCoordinate) => void;
  selectedCoordinate: GeoCoordinate | null;
  isInteracting: boolean;
  northUpRequest: number;
  resetRequest: number;
}

export const EarthGlobe: React.FC<EarthGlobeProps> = ({
  regions,
  onSelectCoordinate,
  selectedCoordinate,
  isInteracting,
  northUpRequest,
  resetRequest,
}) => {
  const earthGroupRef = useRef<THREE.Group>(null);
  const earthMeshRef = useRef<THREE.Mesh>(null);
  const focusTime = useRef(0);
  const focusTarget = useRef<GeoCoordinate | null>(null);
  const camera = useThree(state => state.camera);
  useEffect(() => { focusTarget.current = selectedCoordinate; focusTime.current = selectedCoordinate ? 1.8 : 0; }, [selectedCoordinate]);
  useEffect(() => {
    if (!northUpRequest || !earthGroupRef.current) return;
    const local = earthGroupRef.current.worldToLocal(camera.getWorldPosition(new THREE.Vector3()));
    focusTarget.current = vector3ToLatLng(local);
    focusTime.current = 1.8;
  }, [northUpRequest, camera]);
  useEffect(() => {
    if (!resetRequest || !earthGroupRef.current) return;
    focusTime.current=0; focusTarget.current=null;
    earthGroupRef.current.quaternion.identity();
  }, [resetRequest]);

  // Load authentic NASA Blue Marble textures from public folder
  const [dayMap, normalMap, specularMap, cloudsMap, landMask] = useLoader(THREE.TextureLoader, [
    '/textures/earth_day_2048.jpg',
    '/textures/earth_normal_2048.jpg',
    '/textures/earth_specular_2048.jpg',
    '/textures/earth_clouds_1024.png',
    '/data/land-mask.png',
  ]);

  // Configure texture parameters
  dayMap.colorSpace = THREE.SRGBColorSpace;
  normalMap.colorSpace = THREE.NoColorSpace;
  specularMap.colorSpace = THREE.NoColorSpace;
  cloudsMap.colorSpace = THREE.SRGBColorSpace;

  // Rotate to the selected location; otherwise the Earth stays still.
  useFrame((state, delta) => {
    if (earthGroupRef.current && focusTarget.current && focusTime.current > 0 && !isInteracting) {
      const target = focusTarget.current;
      const localPoint = latLngToVector3(target.lat, target.lng, 1).normalize();
      const towardCamera = state.camera.getWorldPosition(new THREE.Vector3()).sub(earthGroupRef.current.getWorldPosition(new THREE.Vector3())).normalize();
      // Map both the selected surface normal and its north tangent to the
      // camera-facing normal and screen-up tangent. Aligning only the normals
      // leaves an arbitrary roll, especially after a tilted orbit.
      const localNorth = new THREE.Vector3(0, 1, 0).addScaledVector(localPoint, -localPoint.y);
      if (localNorth.lengthSq() < 1e-12) localNorth.set(0, 0, target.lat >= 0 ? -1 : 1);
      localNorth.normalize();
      const localEast = new THREE.Vector3().crossVectors(localNorth, localPoint).normalize();
      const cameraUp = new THREE.Vector3(0, 1, 0).applyQuaternion(state.camera.getWorldQuaternion(new THREE.Quaternion()));
      const screenEast = new THREE.Vector3().crossVectors(cameraUp, towardCamera).normalize();
      const screenNorth = new THREE.Vector3().crossVectors(towardCamera, screenEast).normalize();
      const source = new THREE.Matrix4().makeBasis(localEast, localNorth, localPoint);
      const destination = new THREE.Matrix4().makeBasis(screenEast, screenNorth, towardCamera);
      const targetOrientation = new THREE.Quaternion().setFromRotationMatrix(destination.multiply(source.invert()));
      earthGroupRef.current.quaternion.slerp(targetOrientation, 1 - Math.exp(-5 * delta));
      focusTime.current -= delta;
    }

  });

  // Handle click on the Earth sphere
  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 5 || e.button !== 0) return;
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
        onClick={handleClick}
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
      <mesh scale={[1.009, 1.009, 1.009]}>
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

      <CellOverlay regions={regions} landMask={landMask} earthGroup={earthGroupRef} onSelectCoordinate={onSelectCoordinate} />
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
