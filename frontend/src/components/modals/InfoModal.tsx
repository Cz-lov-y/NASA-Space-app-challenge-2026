import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Globe2, BookOpen, Layers, AlertTriangle } from 'lucide-react';
import { ModalType } from '../../types/globe';

interface InfoModalProps {
  type: ModalType;
  isOpen: boolean;
  onClose: () => void;
}

export const InfoModal: React.FC<InfoModalProps> = ({ type, isOpen, onClose }) => {
  if (!type) return null;

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm transition-opacity animate-in fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-xl border border-cyan-500/30 bg-space-900/95 p-6 shadow-2xl backdrop-blur-xl duration-200 animate-in zoom-in-95 focus:outline-none">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-cyan-500/20 pb-4">
            <div className="flex items-center gap-2.5">
              {type === 'intro' && <Globe2 className="w-5 h-5 text-nasa-cyan" />}
              {type === 'instructions' && <BookOpen className="w-5 h-5 text-nasa-cyan" />}
              {type === 'methodology' && <Layers className="w-5 h-5 text-nasa-cyan" />}
              <Dialog.Title className="text-lg font-semibold tracking-wide text-white uppercase font-mono">
                {type === 'intro' && 'EarthRisk: The Green Mirage · Mission Overview'}
                {type === 'instructions' && 'Mission Flight Manual · Interactive Controls'}
                {type === 'methodology' && 'Scientific Methodology & Scientific Safeguards'}
              </Dialog.Title>
            </div>
            <Dialog.Close className="rounded-lg p-1.5 text-slate-400 hover:bg-space-800 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </Dialog.Close>
          </div>

          {/* Modal Body */}
          <div className="mt-4 max-h-[70vh] overflow-y-auto pr-2 text-sm text-slate-300 space-y-4 leading-relaxed">
            {type === 'intro' && (
              <>
                <div className="p-3.5 rounded-lg bg-nasa-blue/20 border border-nasa-blue/40 text-cyan-200">
                  <p className="font-medium">
                    NASA Space Apps Challenge 2026 · Toronto Hackathon Project
                  </p>
                  <p className="text-xs text-cyan-300/80 mt-1">
                    Screening Earth observation records for landscape greening accompanied by root-zone soil water depletion.
                  </p>
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">What is the "Green Mirage"?</h4>
                  <p>
                    EarthRisk compares vegetation greenness with modeled soil-water storage to screen for places where greening accompanies declining soil water. A preliminary signal needs scientific review; it does not establish environmental damage, groundwater depletion or causation. The current collection covers six demonstration areas rather than the whole Earth.
                  </p>
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Interdisciplinary Team Architecture</h4>
                  <ul className="list-disc list-inside space-y-1 text-slate-300 text-xs">
                    <li><strong className="text-cyan-300">Member A (Statistics):</strong> OLS & Theil–Sen slope modeling, Mann–Kendall trend divergence tests, and Benjamini–Hochberg adjustments.</li>
                    <li><strong className="text-cyan-300">Member B (NASA Data):</strong> MODIS vegetation and GLDAS hydrological land surface observation pipelines.</li>
                    <li><strong className="text-cyan-300">Member C (Policy Agent):</strong> Candidate policy and scientific sources with citations and explicit review status, requested by the user.</li>
                    <li><strong className="text-cyan-300">Member D (Frontend/Integration):</strong> 3D Earth digital twin, interactive mission telemetry, and dashboard integration.</li>
                  </ul>
                </div>
              </>
            )}

            {type === 'instructions' && (
              <>
                <div className="space-y-3">
                  <div className="flex gap-3 items-start p-3 rounded-lg bg-space-800/60 border border-slate-700/50">
                    <div className="w-7 h-7 rounded-full bg-cyan-500/20 text-nasa-cyan flex items-center justify-center font-mono font-bold text-xs shrink-0">
                      1
                    </div>
                    <div>
                      <p className="font-medium text-white text-sm">3D Globe Navigation</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Click and drag anywhere on the canvas to rotate Earth with momentum. Use your mouse scroll wheel or trackpad pinch to zoom smoothly between bounded limits.
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-3 items-start p-3 rounded-lg bg-space-800/60 border border-slate-700/50">
                    <div className="w-7 h-7 rounded-full bg-cyan-500/20 text-nasa-cyan flex items-center justify-center font-mono font-bold text-xs shrink-0">
                      2
                    </div>
                    <div>
                      <p className="font-medium text-white text-sm">Inspect Geographic Coordinates</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Click anywhere on the globe surface to sample exact geographic coordinates. An animated telemetry pin will lock to that position, and the Earth will smoothly slide left to open the detailed telemetry drawer.
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-3 items-start p-3 rounded-lg bg-space-800/60 border border-slate-700/50">
                    <div className="w-7 h-7 rounded-full bg-cyan-500/20 text-nasa-cyan flex items-center justify-center font-mono font-bold text-xs shrink-0">
                      3
                    </div>
                    <div>
                      <p className="font-medium text-white text-sm">Target Hotspots</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Use the "Hotspots" dropdown in the top HUD to jump directly to benchmark ecological transition zones (such as the Synthetic Demo Region, Aral Sea, or Sahel).
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-3 items-start p-3 rounded-lg bg-space-800/60 border border-slate-700/50">
                    <div className="w-7 h-7 rounded-full bg-cyan-500/20 text-nasa-cyan flex items-center justify-center font-mono font-bold text-xs shrink-0">
                      4
                    </div>
                    <div>
                      <p className="font-medium text-white text-sm">Deselecting & Centering</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Clicking the empty starfield space or pressing the "Close" button on the drawer smoothly returns the Earth to its centered viewing position.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}

            {type === 'methodology' && (
              <>
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 flex gap-2.5 items-start">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <strong className="block text-amber-300 font-semibold mb-0.5">Scientific Safeguard Protocol</strong>
                    An empirical divergence signal (increasing NDVI + declining moisture) is a screening indicator only. It does not establish proof of ecological catastrophe or agricultural causality.
                  </div>
                </div>

                <div>
                  <h4 className="text-white font-medium mb-1">Zero Coordinate Fabrication Guarantee</h4>
                  <p className="text-xs text-slate-300">
                    In compliance with NASA Space Apps standards, clicking arbitrary points on Earth reveals their exact geographic coordinates, but will never hallucinate or invent synthetic environmental observations for unvalidated regions. Only registered regions with verified pipelines will display trend data.
                  </p>
                </div>

                <div>
                  <h4 className="text-white font-medium mb-1">Statistical Framework (Member A Contract)</h4>
                  <p className="text-xs text-slate-300">
                    Divergence classification requires eight complete common calendar years. Trends are computed via Ordinary Least Squares and Theil–Sen non-parametric estimators with Mann–Kendall monotonic trend tests and False Discovery Rate control.
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Footer */}
          <div className="mt-6 flex justify-end border-t border-slate-800 pt-3">
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-nasa-blue text-white text-xs font-medium hover:bg-blue-700 transition-colors"
            >
              Close
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
