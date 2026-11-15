import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { ThreeEvent } from '@react-three/fiber';
import { SelectedLocation, GeoCoordinate } from '../../types/globe';
import { latLngToVector3, vector3ToLatLng } from '../../utils/coordinates';
import { signalColor } from '../../utils/signalColors';

interface CellOverlayProps {
  regions: SelectedLocation[];
  landMask: THREE.Texture;
  earthGroup: React.RefObject<THREE.Group>;
  onSelectCoordinate: (coordinate: GeoCoordinate) => void;
}

/** Batch native cell polygons by color; alpha-map removes ocean from coastal cells. */
export function CellOverlay({ regions, landMask, earthGroup, onSelectCoordinate }: CellOverlayProps) {
  const layers = useMemo(() => {
    const grouped = new Map<string, {positions: number[]; uvs: number[]}>();
    for (const region of regions) {
      if (!region.hasObservationalData || region.resolutionDegrees !== 0.25 || !region.bbox) continue;
      const [w,s,e,n]=region.bbox;
      if (![w,s,e,n].every(Number.isFinite) || w>=e || s>=n) continue;
      const color=signalColor(region.screeningStatus);
      const group=grouped.get(color) || {positions: [], uvs: []};
      for (const [lon,lat] of [[w,s],[e,s],[e,n],[w,s],[e,n],[w,n]]) {
        const p=latLngToVector3(lat,lon,1.012);
        group.positions.push(p.x,p.y,p.z);
        group.uvs.push((lon+180)/360,(lat+90)/180);
      }
      grouped.set(color,group);
    }
    return [...grouped].map(([color,data]) => {
      const geometry=new THREE.BufferGeometry();
      geometry.setAttribute('position',new THREE.Float32BufferAttribute(data.positions,3));
      geometry.setAttribute('uv',new THREE.Float32BufferAttribute(data.uvs,2));
      geometry.computeBoundingSphere();
      return {color,geometry};
    });
  },[regions]);
  useEffect(() => () => { layers.forEach(layer => layer.geometry.dispose()); },[layers]);
  const select=(event: ThreeEvent<MouseEvent>) => {
    if (event.delta>5 || event.button!==0 || !earthGroup.current) return;
    event.stopPropagation();
    onSelectCoordinate(vector3ToLatLng(earthGroup.current.worldToLocal(event.point.clone())));
  };
  return <>{layers.map(layer => <mesh key={layer.color} geometry={layer.geometry} onClick={select}>
    <meshBasicMaterial color={layer.color} alphaMap={landMask} alphaTest={0.1} transparent opacity={0.55}
      depthWrite={false} side={THREE.DoubleSide} />
  </mesh>)}</>;
}
