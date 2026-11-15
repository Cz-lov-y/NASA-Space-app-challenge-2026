import React, { useRef, useState, Suspense } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { EarthGlobe } from './EarthGlobe';
import { Starfield } from './Starfield';
import { GeoCoordinate, SelectedLocation } from '../../types/globe';
import { Compass, Plus, Minus, RotateCcw } from 'lucide-react';
import { latLngToVector3 } from '../../utils/coordinates';

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
  northUpRequest: number;
  resetRequest: number;
}

const SceneRig: React.FC<SceneRigProps> = ({
  regions,
  selectedCoordinate,
  onSelectCoordinate,
  isInteracting,
  northUpRequest,
  resetRequest,
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
        northUpRequest={northUpRequest}
        resetRequest={resetRequest}
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
  const [northUpRequest, setNorthUpRequest] = useState(0);
  const [resetRequest, setResetRequest] = useState(0);
  const zoom = (factor: number) => {
    const controls=controlsRef.current;
    if (!controls) return;
    const offset=controls.object.position.clone().sub(controls.target);
    offset.clampLength(controls.minDistance, controls.maxDistance);
    offset.setLength(THREE.MathUtils.clamp(offset.length()*factor, controls.minDistance, controls.maxDistance));
    controls.object.position.copy(controls.target).add(offset);
    controls.update();
  };
  const resetView = () => {
    onDeselect();
    controlsRef.current?.reset();
    setResetRequest(value => value+1);
  };

  // Deselect when clicking background empty space
  const handleMissedClick = () => {
    if (selectedCoordinate) {
      onDeselect();
    }
  };

  return (
    <div className="w-full h-full absolute inset-0 z-0">
      <Canvas
        camera={{ position: latLngToVector3(45, -105, 2.5).toArray(), fov: 45, near: 0.1, far: 1000 }}
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
            northUpRequest={northUpRequest}
            resetRequest={resetRequest}
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
      <div className="fixed bottom-5 left-4 z-30 flex items-center gap-1 rounded-xl border border-slate-300 bg-white/95 p-1 shadow-lg" aria-label="Globe controls">
        <button type="button" onClick={() => setNorthUpRequest(value => value+1)} className="flex items-center gap-1 rounded-lg px-2.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100" title="Turn north up"><Compass size={16} />North up</button>
        <button type="button" onClick={() => zoom(0.75)} className="rounded-lg p-2 text-slate-700 hover:bg-slate-100" aria-label="Zoom in" title="Zoom in"><Plus size={16} /></button>
        <button type="button" onClick={() => zoom(1.33)} className="rounded-lg p-2 text-slate-700 hover:bg-slate-100" aria-label="Zoom out" title="Zoom out"><Minus size={16} /></button>
        <button type="button" onClick={resetView} className="rounded-lg p-2 text-slate-700 hover:bg-slate-100" aria-label="Reset view" title="Reset view"><RotateCcw size={16} /></button>
      </div>
    </div>
  );
};
