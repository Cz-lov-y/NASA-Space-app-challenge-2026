import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

interface StarfieldProps {
  count?: number;
}

export const Starfield: React.FC<StarfieldProps> = ({ count = 4200 }) => {
  const pointsRef = useRef<THREE.Points>(null);

  // Soft circular star point texture created dynamically
  const starTexture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
      gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
      gradient.addColorStop(0.25, 'rgba(215, 235, 255, 0.85)');
      gradient.addColorStop(0.6, 'rgba(120, 180, 255, 0.25)');
      gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, 32, 32);
    }
    const texture = new THREE.CanvasTexture(canvas);
    return texture;
  }, []);

  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);

    const colorPalette = [
      new THREE.Color('#ffffff'), // pure white
      new THREE.Color('#d4e8ff'), // icy blue
      new THREE.Color('#a8d1ff'), // deep blue-white
      new THREE.Color('#fff2cc'), // soft warm stellar yellow
      new THREE.Color('#ffd1b3'), // soft orange giant
    ];

    for (let i = 0; i < count; i++) {
      // Distribute stars on a sphere radius between 35 and 130
      const radius = 35 + Math.random() * 95;
      const theta = 2 * Math.PI * Math.random();
      const phi = Math.acos(2 * Math.random() - 1);

      pos[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = radius * Math.cos(phi);

      const color = colorPalette[Math.floor(Math.random() * colorPalette.length)];
      const brightness = 0.4 + Math.random() * 0.6;
      col[i * 3] = color.r * brightness;
      col[i * 3 + 1] = color.g * brightness;
      col[i * 3 + 2] = color.b * brightness;
    }

    return { positions: pos, colors: col };
  }, [count]);

  // Subtle continuous orbital drift
  useFrame((_, delta) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y += delta * 0.004;
      pointsRef.current.rotation.x += delta * 0.0015;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={1.6}
        map={starTexture}
        vertexColors
        transparent
        opacity={0.9}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};
