import React, { useMemo } from 'react';
import * as THREE from 'three';

// Inner atmospheric rim (visible as soft blue haze hugging the horizon)
const innerAtmosphereVertex = `
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vNormal = normalize(normalMatrix * normal);
  vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const innerAtmosphereFragment = `
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vec3 viewDir = normalize(-vPosition);
  float dotNV = dot(vNormal, viewDir);
  // Strongest at grazing angles (edge of the earth), completely clear in the center
  float rim = 1.0 - clamp(dotNV, 0.0, 1.0);
  float intensity = pow(rim, 3.2) * 0.85;

  // NASA atmospheric Rayleigh blue
  vec3 atmosphereColor = vec3(0.2, 0.65, 1.0);
  gl_FragColor = vec4(atmosphereColor, intensity);
}
`;

// Outer atmospheric glow (soft dissipation extending into space)
const outerGlowVertex = `
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vNormal = normalize(normalMatrix * normal);
  vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const outerGlowFragment = `
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vec3 viewDir = normalize(-vPosition);
  // For BackSide, normal points inwards toward center
  float intensity = pow(0.65 - dot(vNormal, vec3(0, 0, 1.0)), 2.0);
  intensity = clamp(intensity, 0.0, 0.5);

  vec3 glowColor = vec3(0.05, 0.45, 0.95);
  gl_FragColor = vec4(glowColor, intensity * 0.6);
}
`;

export const Atmosphere: React.FC = () => {
  const innerShader = useMemo(() => {
    return {
      vertexShader: innerAtmosphereVertex,
      fragmentShader: innerAtmosphereFragment,
      blending: THREE.AdditiveBlending,
      side: THREE.FrontSide,
      transparent: true,
      depthWrite: false,
    };
  }, []);

  const outerShader = useMemo(() => {
    return {
      vertexShader: outerGlowVertex,
      fragmentShader: outerGlowFragment,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      transparent: true,
      depthWrite: false,
    };
  }, []);

  return (
    <group>
      {/* Delicate Horizon Haze */}
      <mesh scale={[1.018, 1.018, 1.018]}>
        <sphereGeometry args={[1, 64, 64]} />
        <shaderMaterial
          args={[innerShader]}
          transparent
          depthWrite={false}
          side={THREE.FrontSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Outer Soft Corona */}
      <mesh scale={[1.055, 1.055, 1.055]}>
        <sphereGeometry args={[1, 64, 64]} />
        <shaderMaterial
          args={[outerShader]}
          transparent
          depthWrite={false}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  );
};
