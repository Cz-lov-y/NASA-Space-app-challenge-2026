import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { latLngToVector3 } from '../../utils/coordinates';

interface LocationPinProps {
  lat: number;
  lng: number;
  radius?: number;
}

export const LocationPin: React.FC<LocationPinProps> = ({ lat, lng, radius = 1.0 }) => {
  const pinGroupRef = useRef<THREE.Group>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const beaconRef = useRef<THREE.Mesh>(null);

  // Calculate position and normal on the sphere
  const { position, quaternion } = useMemo(() => {
    const pos = latLngToVector3(lat, lng, radius);
    const normal = pos.clone().normalize();
    const q = new THREE.Quaternion();
    // Default cylinder/ring lies in XZ plane or points along +Y
    q.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
    return { position: pos, quaternion: q };
  }, [lat, lng, radius]);

  // Subtle continuous pulsation animation
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();

    // Pulse ring 1
    if (ring1Ref.current) {
      const scale1 = 1 + (t % 1.5) * 1.8;
      ring1Ref.current.scale.set(scale1, scale1, scale1);
      const mat = ring1Ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = Math.max(0, 1 - (t % 1.5) / 1.5) * 0.8;
    }

    // Pulse ring 2 (delayed phase)
    if (ring2Ref.current) {
      const scale2 = 1 + ((t + 0.75) % 1.5) * 1.8;
      ring2Ref.current.scale.set(scale2, scale2, scale2);
      const mat = ring2Ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = Math.max(0, 1 - ((t + 0.75) % 1.5) / 1.5) * 0.6;
    }

    // Gentle vertical bob for beacon diamond
    if (beaconRef.current) {
      beaconRef.current.position.y = 0.08 + Math.sin(t * 3) * 0.008;
    }
  });

  return (
    <group ref={pinGroupRef} position={position} quaternion={quaternion}>
      {/* Surface Base Rings (oriented perpendicular to normal, rotated to lie flat) */}
      <mesh ref={ring1Ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]}>
        <ringGeometry args={[0.016, 0.024, 32]} />
        <meshBasicMaterial
          color="#00E5FF"
          side={THREE.DoubleSide}
          transparent
          opacity={0.8}
          depthWrite={false}
        />
      </mesh>

      <mesh ref={ring2Ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]}>
        <ringGeometry args={[0.012, 0.020, 32]} />
        <meshBasicMaterial
          color="#FC3D21"
          side={THREE.DoubleSide}
          transparent
          opacity={0.6}
          depthWrite={false}
        />
      </mesh>

      {/* Surface Contact Dot */}
      <mesh position={[0, 0.004, 0]}>
        <sphereGeometry args={[0.009, 16, 16]} />
        <meshBasicMaterial color="#FC3D21" />
      </mesh>

      {/* Vertical Holographic Telemetry Laser Beam */}
      <mesh position={[0, 0.04, 0]}>
        <cylinderGeometry args={[0.0018, 0.0018, 0.08, 16]} />
        <meshBasicMaterial
          color="#00E5FF"
          transparent
          opacity={0.85}
          depthWrite={false}
        />
      </mesh>

      {/* Floating Beacon Diamond Head */}
      <mesh ref={beaconRef} position={[0, 0.08, 0]} rotation={[0, Math.PI / 4, 0]}>
        <octahedronGeometry args={[0.012, 0]} />
        <meshStandardMaterial
          color="#00E5FF"
          emissive="#00B4D8"
          emissiveIntensity={1.2}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>
    </group>
  );
};
