import React, { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle } from 'lucide-react';

const WaterSystemsDominos = () => {
  const [hoveredSystem, setHoveredSystem] = useState(null);
  const [animationState, setAnimationState] = useState('idle'); // idle, animating, fallen
  const [resetKey, setResetKey] = useState(0);

  // Start animation on mount
  useEffect(() => {
    const timer = setTimeout(() => setAnimationState('animating'), 500);
    return () => clearTimeout(timer);
  }, [resetKey]);

  const handleReset = () => {
    setAnimationState('idle');
    setResetKey(prev => prev + 1);
  };

  // Data from CSV
  const systems = [
    {
      id: 0,
      name: 'Lake Mead',
      region: 'USA Southwest',
      climate: '41-55% inflow below average',
      infrastructure: 'Aging dams/power loss',
      capacity: 'Critical',
      timeline: 1.5, // years (1-2)
      political: '7-state deadlock (expires 2026)',
      geopolitical: 'None',
      population: '3+ million users'
    },
    {
      id: 1,
      name: 'Taleghan',
      region: 'Iran',
      climate: '40-51% below normal',
      infrastructure: 'Massive pipeline leakage',
      capacity: 'Critical',
      timeline: 2.5, // years (2-3)
      political: 'Slow government response',
      geopolitical: 'None',
      population: 'Regional water supply'
    },
    {
      id: 2,
      name: 'Nile',
      region: 'Egypt/Sudan/Ethiopia',
      climate: 'Upstream dam stress',
      infrastructure: 'Multiple infrastructure points',
      capacity: 'Stressed',
      timeline: 3.5, // years (2-5)
      political: 'Egypt-Sudan-Ethiopia tensions',
      geopolitical: 'YES',
      population: '100+ million Egyptians'
    },
    {
      id: 3,
      name: 'Indus',
      region: 'Pakistan/India',
      climate: 'Glaciers melting + monsoon erratic',
      infrastructure: 'Dams at dead pool',
      capacity: 'Critical',
      timeline: 5, // years (3-7)
      political: 'Pakistan helpless',
      geopolitical: 'YES',
      population: '230+ million Pakistanis'
    }
  ];

  // Calculate rotation angle based on timeline
  const getRotation = (timelineYears) => {
    // Faster systems rotate more per unit time
    const baseDelay = timelineYears * 1000; // milliseconds
    const maxRotation = 90;
    return maxRotation; // Will be animated
  };

  return (
    <div className="w-full min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col p-8">
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-orange-400 mb-2">
            Global Water Systems Crisis
          </h1>
          <p className="text-slate-300 text-lg">Cascading infrastructure collapse scenarios</p>
        </div>

        {/* Dominos Container - More space for falling */}
        <div
          className="flex-1 flex items-center justify-center gap-8 perspective overflow-hidden pb-16"
          onMouseEnter={() => animationState === 'animating' && setAnimationState('paused')}
          onMouseLeave={() => animationState === 'paused' && setAnimationState('animating')}
        >
          {systems.map((system, idx) => {
            const isHovered = hoveredSystem === idx;
            const capacityIsRed = system.capacity === 'Critical';
            const hasGeopoliticalRisk = system.geopolitical === 'YES';
            
            return (
              <div
                key={`${system.id}-${resetKey}`}
                className="relative"
                style={{
                  perspective: '1000px',
                  width: '140px',
                  height: '320px'
                }}
              >
                {/* Domino */}
                <div
                  className={`
                    absolute inset-0 rounded-lg transition-all duration-200
                    ${isHovered ? 'ring-2 ring-cyan-400' : ''}
                    cursor-pointer shadow-2xl
                  `}
                  style={{
                    background: `linear-gradient(135deg, rgba(30, 58, 138, 0.8) 0%, rgba(6, 182, 212, 0.5) 100%)`,
                    backdropFilter: 'blur(10px)',
                    border: '2px solid rgba(6, 182, 212, 0.5)',
                    boxShadow: '0 12px 40px rgba(0, 0, 0, 0.6)',
                    animation: animationState === 'animating' ? `domino-fall-${idx} 12s ease-in-out forwards` : 'none',
                    transformOrigin: 'bottom center'
                  }}
                  onMouseEnter={() => setHoveredSystem(idx)}
                  onMouseLeave={() => setHoveredSystem(null)}
                >
                  {/* Center dividing line (domino characteristic) */}
                  <div className="absolute top-0 bottom-0 left-1/2 transform -translate-x-1/2 w-1 bg-gradient-to-b from-slate-700 to-slate-800 opacity-60 z-0"></div>

                  {/* Content Inside Domino - Counter-rotates to stay readable */}
                  <div 
                    className="h-full w-full flex flex-col justify-between relative z-20 pointer-events-none"
                    style={{
                      animation: animationState === 'animating' ? `content-counter-rotate-${idx} 12s ease-in-out forwards` : 'none',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between'
                    }}
                  >
                    {/* System Name */}
                    <div>
                      <h3 className="text-sm font-bold text-cyan-200 mb-1 drop-shadow-lg">
                        {system.name}
                      </h3>
                      <p className="text-xs text-slate-200 drop-shadow-md">{system.region}</p>
                    </div>

                    {/* Capacity Bar */}
                    <div className="space-y-2">
                      <div className="text-xs text-slate-200 font-semibold drop-shadow-md">
                        Capacity
                      </div>
                      <div className="w-full h-3 bg-slate-700 rounded-full overflow-hidden border border-slate-600">
                        <div
                          className={`h-full rounded-full transition-all ${
                            capacityIsRed
                              ? 'bg-gradient-to-r from-red-600 to-red-500'
                              : 'bg-gradient-to-r from-yellow-600 to-yellow-500'
                          }`}
                          style={{ width: '85%' }}
                        ></div>
                      </div>
                    </div>

                    {/* Timeline */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-200 drop-shadow-md">
                        Crisis in {system.timeline}y
                      </span>
                      <div className="text-sm font-bold text-orange-300 drop-shadow-lg">
                        {Math.round(system.timeline * 365)}d
                      </div>
                    </div>

                    {/* Population & Risk */}
                    <div className="flex items-center justify-between pt-2 border-t border-slate-600">
                      <span className="text-xs text-slate-200 line-clamp-2 drop-shadow-md">
                        {system.population}
                      </span>
                      {hasGeopoliticalRisk ? (
                        <div className="flex items-center gap-1">
                          <AlertCircle className="w-5 h-5 text-red-400 animate-pulse drop-shadow-lg" />
                          <span className="text-xs text-red-300 font-semibold drop-shadow-md">Risk</span>
                        </div>
                      ) : (
                        <CheckCircle className="w-5 h-5 text-green-400 drop-shadow-lg" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Hover Tooltip */}
                {isHovered && (
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-4 w-64 bg-slate-950 border border-cyan-500 rounded-lg p-4 text-sm text-slate-200 z-50 shadow-2xl">
                    <div className="font-semibold text-cyan-400 mb-2">{system.name}</div>
                    <div className="space-y-1 text-xs">
                      <p><span className="text-slate-400">Region:</span> {system.region}</p>
                      <p><span className="text-slate-400">Timeline:</span> {system.timeline}y</p>
                      <p><span className="text-slate-400">Population:</span> {system.population}</p>
                      <p><span className="text-slate-400">Political:</span> {system.political}</p>
                      <p><span className="text-slate-400">Geopolitical:</span> {system.geopolitical}</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Reset Button */}
        <div className="flex justify-center mb-8">
          <button
            onClick={handleReset}
            className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-lg transition-colors"
          >
            Reset Animation
          </button>
        </div>
      </div>

      {/* Legend & Info - Fixed at bottom */}
      <div className="mt-auto grid grid-cols-2 gap-8 text-sm text-slate-300 bg-slate-900 bg-opacity-50 rounded-lg p-6 backdrop-blur-sm">
        <div>
          <h4 className="font-semibold text-cyan-400 mb-3">Color Legend</h4>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-red-600"></div>
              <span>Critical Capacity</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-yellow-600"></div>
              <span>Stressed Capacity</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span>Geopolitical Risk</span>
            </div>
          </div>
        </div>
        <div>
          <h4 className="font-semibold text-cyan-400 mb-3">Cascade Timeline</h4>
          <p className="text-xs text-slate-400">
            Click "Reset Animation" to start the cascade. Dominos fall in sequence based on crisis urgency. Hover to pause.
          </p>
        </div>
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes domino-fall-0 {
          0% { transform: rotateZ(0deg); }
          30% { transform: rotateZ(0deg); }
          60% { transform: rotateZ(90deg); }
          100% { transform: rotateZ(90deg); }
        }
        
        @keyframes domino-fall-1 {
          0% { transform: rotateZ(0deg); }
          40% { transform: rotateZ(0deg); }
          70% { transform: rotateZ(90deg); }
          100% { transform: rotateZ(90deg); }
        }
        
        @keyframes domino-fall-2 {
          0% { transform: rotateZ(0deg); }
          55% { transform: rotateZ(0deg); }
          80% { transform: rotateZ(90deg); }
          100% { transform: rotateZ(90deg); }
        }
        
        @keyframes domino-fall-3 {
          0% { transform: rotateZ(0deg); }
          65% { transform: rotateZ(0deg); }
          90% { transform: rotateZ(90deg); }
          100% { transform: rotateZ(90deg); }
        }

        @keyframes content-counter-rotate-0 {
          0% { transform: rotateZ(0deg); }
          30% { transform: rotateZ(0deg); }
          60% { transform: rotateZ(-90deg); }
          100% { transform: rotateZ(-90deg); }
        }
        
        @keyframes content-counter-rotate-1 {
          0% { transform: rotateZ(0deg); }
          40% { transform: rotateZ(0deg); }
          70% { transform: rotateZ(-90deg); }
          100% { transform: rotateZ(-90deg); }
        }
        
        @keyframes content-counter-rotate-2 {
          0% { transform: rotateZ(0deg); }
          55% { transform: rotateZ(0deg); }
          80% { transform: rotateZ(-90deg); }
          100% { transform: rotateZ(-90deg); }
        }
        
        @keyframes content-counter-rotate-3 {
          0% { transform: rotateZ(0deg); }
          65% { transform: rotateZ(0deg); }
          90% { transform: rotateZ(-90deg); }
          100% { transform: rotateZ(-90deg); }
        }
      `}</style>
    </div>
  );
};

export default WaterSystemsDominos;
