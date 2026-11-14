import React, { useRef, useState, Suspense } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { EarthGlobe } from './EarthGlobe';
import { Starfield } from './Starfield';
import { GeoCoordinate } from '../../types/globe';

interface EarthCanvasProps {
  selectedCoordinate: GeoCoordinate | null;
  onSelectCoordinate: (coord: GeoCoordinate) => void;
  onDeselect: () => void;
}

// Inner scene component to manage smooth viewport translation
interface SceneRigProps {
  selectedCoordinate: GeoCoordinate | null;
  onSelectCoordinate: (coord: GeoCoordinate) => void;
  isInteracting: boolean;
}

const SceneRig: React.FC<SceneRigProps> = ({
  selectedCoordinate,
  onSelectCoordinate,
  isInteracting,
}) => {
  const globeRootRef = useRef<THREE.Group>(null);

  // Smoothly shift Earth group to the left when a location is selected
  useFrame((_, delta) => {
    if (globeRootRef.current) {
      // Offset left (-0.45 in world units) to make room for right-side drawer
      const targetX = selectedCoordinate ? -0.45 : 0;
      globeRootRef.current.position.x = THREE.MathUtils.damp(
        globeRootRef.current.position.x,
        targetX,
        4.5,
        delta
      );
    }
  });

  return (
    <group ref={globeRootRef}>
      <EarthGlobe
        onSelectCoordinate={onSelectCoordinate}
        selectedCoordinate={selectedCoordinate}
        isInteracting={isInteracting}
      />
    </group>
  );
};

export const EarthCanvas: React.FC<EarthCanvasProps> = ({
  selectedCoordinate,
  onSelectCoordinate,
  onDeselect,
}) => {
  const [isInteracting, setIsInteracting] = useState(false);
  const controlsRef = useRef<OrbitControlsImpl>(null);

  // Deselect when clicking background empty space
  const handleMissedClick = () => {
    if (selectedCoordinate) {
      onDeselect();
    }
  };

  return (
    <div className="w-full h-full absolute inset-0 z-0">
      <Canvas
        camera={{ position: [0, 0, 2.5], fov: 45, near: 0.1, far: 1000 }}
        onPointerDown={(e) => {
          // If clicked canvas element directly without hitting 3D object
          if (e.target === e.currentTarget) {
            handleMissedClick();
          }
        }}
        gl={{
          antialias: true,
          powerPreference: 'high-performance',
          alpha: false,
        }}
      >
        <color attach="background" args={['#020617']} />

        {/* Space Lighting - Authentic Solar & Earth Illumination */}
        <ambientLight intensity={0.55} color="#102a45" />
        <directionalLight
          position={[5, 3, 4]}
          intensity={2.8}
          color="#ffffff"
        />
        <directionalLight
          position={[-3, 1, 3]}
          intensity={0.6}
          color="#6ea8d8"
        />
        <directionalLight
          position={[0, -4, -2]}
          intensity={0.25}
          color="#00e5ff"
        />

        {/* Background Starfield */}
        <Starfield count={3800} />

        {/* 3D Earth Globe with Texture Suspension */}
        <Suspense fallback={null}>
          <SceneRig
            selectedCoordinate={selectedCoordinate}
            onSelectCoordinate={onSelectCoordinate}
            isInteracting={isInteracting}
          />
        </Suspense>

        {/* Camera Orbit Controls with bounded zoom and inertia */}
        <OrbitControls
          ref={controlsRef}
          enableDamping
          dampingFactor={0.05}
          minDistance={1.35}
          maxDistance={4.2}
          enablePan={false}
          rotateSpeed={0.65}
          zoomSpeed={0.75}
          onStart={() => setIsInteracting(true)}
          onEnd={() => setIsInteracting(false)}
        />
      </Canvas>
    </div>
  );
};
