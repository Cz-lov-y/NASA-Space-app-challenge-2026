import React, { useRef, useState, Suspense } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { EarthGlobe } from './EarthGlobe';
import { Starfield } from './Starfield';
import { GeoCoordinate, SelectedLocation } from '../../types/globe';

interface EarthCanvasProps {
  regions: SelectedLocation[];
  selectedCoordinate: GeoCoordinate | null;
  onSelectCoordinate: (coord: GeoCoordinate) => void;
  onDeselect: () => void;
}

// Inner scene component to manage smooth viewport translation
interface SceneRigProps {
  regions: SelectedLocation[];
  selectedCoordinate: GeoCoordinate | null;
  onSelectCoordinate: (coord: GeoCoordinate) => void;
  isInteracting: boolean;
}

const SceneRig: React.FC<SceneRigProps> = ({
  regions,
  selectedCoordinate,
  onSelectCoordinate,
  isInteracting,
}) => {
  const globeRootRef = useRef<THREE.Group>(null);
  const cameraOffset = useRef(new THREE.Vector3());

  // Smoothly shift Earth group to the left when a location is selected
  useFrame(({ camera }, delta) => {
    if (globeRootRef.current) {
      // Offset left (-0.45 in world units) to make room for right-side drawer
      const targetX = selectedCoordinate ? -0.45 : 0;
      globeRootRef.current.position.x = THREE.MathUtils.damp(
        globeRootRef.current.position.x,
        targetX,
        4.5,
        delta
      );
      // OrbitControls measures zoom from its fixed target, but the globe moves
      // sideways when a panel opens. Keep the camera and its near plane outside
      // the actual shifted surface at every orbit angle.
      const near = camera instanceof THREE.PerspectiveCamera || camera instanceof THREE.OrthographicCamera ? camera.near : 0.1;
      const minimum = 1 + near + 0.025;
      const offset = cameraOffset.current.subVectors(camera.position, globeRootRef.current.position);
      if (offset.lengthSq() < minimum * minimum) {
        if (offset.lengthSq() < 1e-12) offset.set(0, 0, 1);
        camera.position.copy(globeRootRef.current.position).add(offset.setLength(minimum));
        camera.lookAt(0, 0, 0);
      }
    }
  });

  return (
    <group ref={globeRootRef}>
      <EarthGlobe
        regions={regions}
        onSelectCoordinate={onSelectCoordinate}
        selectedCoordinate={selectedCoordinate}
        isInteracting={isInteracting}
      />
    </group>
  );
};

export const EarthCanvas: React.FC<EarthCanvasProps> = ({
  regions,
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
        onPointerMissed={handleMissedClick}
        gl={{
          antialias: true,
          powerPreference: 'high-performance',
          alpha: false,
        }}
      >
        <color attach="background" args={['#c8e5f2']} />

        {/* Space Lighting - Authentic Solar & Earth Illumination */}
        <ambientLight intensity={1.5} color="#ffffff" />
        <directionalLight
          position={[5, 3, 4]}
          intensity={2.0}
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
        <Starfield count={500} />

        {/* 3D Earth Globe with Texture Suspension */}
        <Suspense fallback={null}>
          <SceneRig
            regions={regions}
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
          minDistance={1.125}
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
