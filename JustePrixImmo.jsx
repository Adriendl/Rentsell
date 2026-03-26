import React, { useState, useReducer, useRef, useEffect, useCallback } from 'react';
import {
  ChevronLeft, ChevronRight, ChevronDown, Timer, Home, MapPin, Trophy,
  Play, Maximize, RotateCcw, Target, Clock, TrendingUp,
  TrendingDown, Award, ArrowRight, Info, ExternalLink, Loader2,
  Map, Building2, Camera
} from 'lucide-react';
import APARTMENTS_DB from './apartments.json';

// ============================================================
// METRO AREAS — proximity-based city grouping
// ============================================================

const METRO_AREAS = [
  { key: 'paris',      label: 'Paris',      emoji: '🗼', lat: 48.8566, lng: 2.3522, radius: 25 },
  { key: 'lyon',       label: 'Lyon',       emoji: '🦁', lat: 45.7640, lng: 4.8357, radius: 20 },
  { key: 'marseille',  label: 'Marseille',  emoji: '⛵', lat: 43.2965, lng: 5.3698, radius: 25 },
  { key: 'bordeaux',   label: 'Bordeaux',   emoji: '🍷', lat: 44.8378, lng: -0.5792, radius: 20 },
  { key: 'toulouse',   label: 'Toulouse',   emoji: '🚀', lat: 43.6047, lng: 1.4442, radius: 20 },
  { key: 'nantes',     label: 'Nantes',     emoji: '🐘', lat: 47.2184, lng: -1.5536, radius: 20 },
  { key: 'lille',      label: 'Lille',       emoji: '🧱', lat: 50.6292, lng: 3.0573, radius: 20 },
  { key: 'nice',       label: 'Nice',       emoji: '🌴', lat: 43.7102, lng: 7.2620, radius: 25 },
  { key: 'montpellier',label: 'Montpellier',emoji: '☀️', lat: 43.6108, lng: 3.8767, radius: 20 },
  { key: 'strasbourg', label: 'Strasbourg', emoji: '🥨', lat: 48.5734, lng: 7.7521, radius: 20 },
];

/** Haversine distance in km between two lat/lng points */
function haversineKm(lat1, lng1, lat2, lng2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Filter listings that fall within a metro area's radius */
function listingsForMetro(listings, metro) {
  return listings.filter((l) =>
    haversineKm(l.lat, l.lng, metro.lat, metro.lng) <= metro.radius
  );
}

/** Build available metros from the actual data (>= 3 listings) */
function getAvailableMetros(listings) {
  return METRO_AREAS
    .map((m) => ({ ...m, count: listingsForMetro(listings, m).length }))
    .filter((m) => m.count >= 3);
}

// ============================================================
// API FETCH — with silent fallback to static JSON
// ============================================================

const API_BASE = import.meta.env.VITE_API_URL || '';

async function fetchListings(count = 50) {
  if (API_BASE) {
    try {
      const resp = await fetch(`${API_BASE}/listings?limit=${count}&random=true`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.length > 0) return data;
      }
    } catch (_) { /* fallback below */ }
  }
  return [...APARTMENTS_DB];
}

// ============================================================
// HELPERS
// ============================================================

const ROUNDS_PER_GAME = 10;
const TIMER_SECONDS = 60;

function shuffleArray(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function formatPrice(n) {
  if (n == null || isNaN(n)) return '0';
  return new Intl.NumberFormat('fr-FR').format(n);
}

function calculateScore(guess, actual, timeRemaining) {
  if (guess === 0 || guess == null) return { precision: 0, timeBonus: 0, total: 0, gap: 100 };
  const gap = Math.abs(guess - actual) / actual * 100;
  let precision = 0;
  if (gap === 0) precision = 1000;
  else if (gap <= 5) precision = 800;
  else if (gap <= 10) precision = 600;
  else if (gap <= 15) precision = 400;
  else if (gap <= 25) precision = 200;
  else if (gap <= 40) precision = 100;
  const timeBonus = Math.floor((timeRemaining / TIMER_SECONDS) * 200);
  return { precision, timeBonus, total: precision + timeBonus, gap: Math.round(gap * 10) / 10 };
}

function getScoreEmoji(gap) {
  if (gap === 0) return { emoji: '🎯', label: 'Parfait !' };
  if (gap <= 5) return { emoji: '🔥', label: 'Excellent !' };
  if (gap <= 10) return { emoji: '💪', label: 'Très bien !' };
  if (gap <= 15) return { emoji: '👍', label: 'Bien !' };
  if (gap <= 25) return { emoji: '🙂', label: 'Pas mal' };
  if (gap <= 40) return { emoji: '😐', label: 'Bof...' };
  return { emoji: '😬', label: 'Raté !' };
}

// ============================================================
// REDUCER
// ============================================================

const initialState = {
  phase: 'menu',
  allListings: [],
  apartments: [],
  selectedMetro: null,
  currentRound: 0,
  timeRemaining: TIMER_SECONDS,
  playerGuess: '',
  roundScore: null,
  totalScore: 0,
  roundHistory: [],
};

function gameReducer(state, action) {
  switch (action.type) {
    case 'SHOW_CITY_SELECT':
      return { ...initialState, phase: 'citySelect', allListings: action.listings };
    case 'START_GAME': {
      let pool = state.allListings;
      if (action.metro) {
        pool = listingsForMetro(pool, action.metro);
      }
      const shuffled = shuffleArray(pool).slice(0, ROUNDS_PER_GAME);
      return {
        ...initialState,
        allListings: state.allListings,
        phase: 'playing',
        apartments: shuffled,
        selectedMetro: action.metro || null,
        currentRound: 0,
        timeRemaining: TIMER_SECONDS,
      };
    }
    case 'TICK':
      return { ...state, timeRemaining: Math.max(0, state.timeRemaining - 1) };
    case 'SET_GUESS':
      return { ...state, playerGuess: action.value };
    case 'SUBMIT_GUESS': {
      const apt = state.apartments[state.currentRound];
      const guess = parseInt(String(action.value).replace(/\s/g, ''), 10) || 0;
      const score = calculateScore(guess, apt.price, state.timeRemaining);
      return {
        ...state,
        phase: 'result',
        playerGuess: guess,
        roundScore: score,
        totalScore: state.totalScore + score.total,
        roundHistory: [
          ...state.roundHistory,
          { apartment: apt, guess, score, round: state.currentRound + 1 },
        ],
      };
    }
    case 'TIME_UP': {
      const apt = state.apartments[state.currentRound];
      const guess = parseInt(String(state.playerGuess).replace(/\s/g, ''), 10) || 0;
      const score = calculateScore(guess, apt.price, 0);
      return {
        ...state,
        phase: 'result',
        playerGuess: guess,
        roundScore: score,
        totalScore: state.totalScore + score.total,
        roundHistory: [
          ...state.roundHistory,
          { apartment: apt, guess, score, round: state.currentRound + 1 },
        ],
      };
    }
    case 'NEXT_ROUND': {
      const nextRound = state.currentRound + 1;
      if (nextRound >= state.apartments.length) {
        return { ...state, phase: 'gameover' };
      }
      return {
        ...state,
        phase: 'playing',
        currentRound: nextRound,
        timeRemaining: TIMER_SECONDS,
        playerGuess: '',
        roundScore: null,
      };
    }
    case 'RESTART':
      return { ...initialState, phase: 'citySelect', allListings: state.allListings };
    default:
      return state;
  }
}

// ============================================================
// COMPONENTS
// ============================================================

function PhotoCarousel({ images }) {
  const [idx, setIdx] = useState(0);
  const touchRef = useRef({ startX: 0, startY: 0 });

  useEffect(() => { setIdx(0); }, [images]);

  const prev = () => setIdx((i) => (i === 0 ? images.length - 1 : i - 1));
  const next = () => setIdx((i) => (i === images.length - 1 ? 0 : i + 1));

  const onTouchStart = (e) => {
    touchRef.current.startX = e.touches[0].clientX;
    touchRef.current.startY = e.touches[0].clientY;
  };

  const onTouchEnd = (e) => {
    const dx = e.changedTouches[0].clientX - touchRef.current.startX;
    const dy = e.changedTouches[0].clientY - touchRef.current.startY;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
      dx < 0 ? next() : prev();
    }
  };

  return (
    <div
      className="relative w-full h-full min-h-[250px] bg-gray-800 rounded-xl overflow-hidden group touch-pan-y"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      {images.map((src, i) => (
        <img
          key={src}
          src={src}
          alt={`Photo ${i + 1}`}
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-500"
          style={{ opacity: i === idx ? 1 : 0 }}
        />
      ))}
      {/* Counter */}
      <div className="absolute top-3 right-3 bg-black/60 text-white text-sm px-3 py-1 rounded-full backdrop-blur-sm">
        {idx + 1} / {images.length}
      </div>
      {/* Arrows */}
      <button
        onClick={prev}
        className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <ChevronLeft size={20} />
      </button>
      <button
        onClick={next}
        className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <ChevronRight size={20} />
      </button>
      {/* Dots */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
        {images.map((_, i) => (
          <button
            key={i}
            onClick={() => setIdx(i)}
            className={`w-2 h-2 rounded-full transition-all ${
              i === idx ? 'bg-emerald-400 w-4' : 'bg-white/50'
            }`}
          />
        ))}
      </div>
    </div>
  );
}

function MapEmbed({ lat, lng, city }) {
  const bbox = `${lng - 0.01},${lat - 0.01},${lng + 0.01},${lat + 0.01}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
  return (
    <div className="relative w-full h-full min-h-[200px] rounded-xl overflow-hidden">
      <iframe
        title="Carte"
        src={src}
        className="w-full h-full border-0"
        loading="lazy"
      />
      <div className="absolute bottom-3 left-3 bg-black/60 backdrop-blur-sm text-white text-sm px-3 py-1.5 rounded-lg flex items-center gap-1.5">
        <MapPin size={14} className="text-emerald-400" />
        {city}
      </div>
    </div>
  );
}

function InfoBadges({ surface, rooms }) {
  return (
    <div className="flex gap-3 flex-wrap">
      <div className="flex items-center gap-2 bg-emerald-500/20 text-emerald-400 px-4 py-2 rounded-lg border border-emerald-500/30">
        <Maximize size={16} />
        <span className="font-bold text-lg">{surface} m²</span>
      </div>
      {rooms && (
        <div className="flex items-center gap-2 bg-emerald-500/20 text-emerald-400 px-4 py-2 rounded-lg border border-emerald-500/30">
          <Home size={16} />
          <span className="font-bold text-lg">{rooms} pièce{rooms > 1 ? 's' : ''}</span>
        </div>
      )}
    </div>
  );
}

function TimerDisplay({ timeRemaining, total }) {
  const pct = (timeRemaining / total) * 100;
  let color = 'bg-emerald-500';
  let textColor = 'text-emerald-400';
  if (timeRemaining <= 10) {
    color = 'bg-red-500';
    textColor = 'text-red-400';
  } else if (timeRemaining <= 30) {
    color = 'bg-orange-500';
    textColor = 'text-orange-400';
  }

  const minutes = Math.floor(timeRemaining / 60);
  const seconds = timeRemaining % 60;

  return (
    <div className="flex items-center gap-3 w-full">
      <Clock size={20} className={textColor} />
      <div className="flex-1 h-3 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-1000 ease-linear`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono font-bold text-lg min-w-[50px] text-right ${textColor} ${timeRemaining <= 10 ? 'animate-pulse' : ''}`}>
        {minutes}:{seconds.toString().padStart(2, '0')}
      </span>
    </div>
  );
}

function PriceInput({ value, onChange, onSubmit, disabled }) {
  const inputRef = useRef(null);

  const handleChange = (e) => {
    const raw = e.target.value.replace(/[^\d]/g, '');
    onChange(raw);
  };

  const displayValue = value ? formatPrice(parseInt(value, 10)) : '';

  const numericValue = parseInt(value, 10) || 0;

  const handleSlider = (e) => {
    onChange(e.target.value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!value || parseInt(value, 10) === 0) return;
    onSubmit(value);
  };



  return (
    <form onSubmit={handleSubmit} className="w-full space-y-3">
      <div className="flex gap-3">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            inputMode="numeric"
            value={displayValue}
            onChange={handleChange}
            disabled={disabled}
            placeholder="Votre estimation..."
            className="w-full bg-gray-800 border-2 border-gray-600 focus:border-emerald-500 text-white text-xl font-bold px-4 py-3 pr-12 rounded-xl outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 font-bold">€</span>
        </div>
        <button
          type="submit"
          disabled={disabled || !value || parseInt(value, 10) === 0}
          className="bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold px-6 py-3 rounded-xl transition-colors flex items-center gap-2"
        >
          <Target size={18} />
          Valider
        </button>
      </div>
      <input
        type="range"
        min="50000"
        max="1200000"
        step="5000"
        value={numericValue || 50000}
        onChange={handleSlider}
        disabled={disabled}
        className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-emerald-500 disabled:opacity-50"
      />
      <div className="flex justify-between text-xs text-gray-500">
        <span>50 000 €</span>
        <span>1 200 000 €</span>
      </div>
    </form>
  );
}

function AnimatedNumber({ target, duration = 1500 }) {
  const [current, setCurrent] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    setCurrent(0);
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));
      if (progress < 1) {
        ref.current = requestAnimationFrame(animate);
      }
    };
    ref.current = requestAnimationFrame(animate);
    return () => { if (ref.current) cancelAnimationFrame(ref.current); };
  }, [target, duration]);

  return <span>{formatPrice(current)} €</span>;
}

function ResultScreen({ roundData, onNext, isLast }) {
  const { apartment, guess, score } = roundData;
  const { emoji, label } = getScoreEmoji(score.gap);
  const diff = guess - apartment.price;

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6 animate-fadeIn">
      <div className="text-center space-y-2">
        <div className="text-6xl">{emoji}</div>
        <h2 className="text-2xl font-bold text-white">{label}</h2>
      </div>

      <div className="bg-gray-800/50 rounded-2xl p-6 space-y-4 border border-gray-700">
        <div className="text-center">
          <p className="text-gray-400 text-sm mb-1">Le vrai prix</p>
          <p className="text-3xl font-bold text-emerald-400">
            <AnimatedNumber target={apartment.price} />
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 text-center">
          <div className="bg-gray-900/50 rounded-xl p-3">
            <p className="text-gray-400 text-xs mb-1">Votre estimation</p>
            <p className="text-lg font-bold text-white">{formatPrice(guess)} €</p>
          </div>
          <div className="bg-gray-900/50 rounded-xl p-3">
            <p className="text-gray-400 text-xs mb-1">Écart</p>
            <p className={`text-lg font-bold flex items-center justify-center gap-1 ${
              score.gap <= 10 ? 'text-emerald-400' : score.gap <= 25 ? 'text-orange-400' : 'text-red-400'
            }`}>
              {diff > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              {score.gap}%
            </p>
          </div>
        </div>

        <div className="border-t border-gray-700 pt-4">
          <div className="flex justify-between items-center text-sm">
            <span className="text-gray-400">Points de précision</span>
            <span className="text-white font-bold">{score.precision}</span>
          </div>
          <div className="flex justify-between items-center text-sm mt-1">
            <span className="text-gray-400">Bonus temps</span>
            <span className="text-white font-bold">+{score.timeBonus}</span>
          </div>
          <div className="flex justify-between items-center text-lg mt-3 pt-3 border-t border-gray-700">
            <span className="text-emerald-400 font-bold">Total du round</span>
            <span className="text-emerald-400 font-bold">{score.total} pts</span>
          </div>
        </div>
      </div>

      {apartment.source && (
        <a
          href={apartment.source}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-2 text-gray-300 hover:text-emerald-400 bg-gray-800/50 hover:bg-gray-800 border border-gray-700 py-3 rounded-xl transition-colors text-sm"
        >
          <ExternalLink size={16} />
          Voir l'annonce originale
        </a>
      )}

      <button
        onClick={onNext}
        className="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-4 rounded-xl transition-colors flex items-center justify-center gap-2 text-lg"
      >
        {isLast ? (
          <>
            <Trophy size={20} />
            Voir le résultat final
          </>
        ) : (
          <>
            Appartement suivant
            <ArrowRight size={20} />
          </>
        )}
      </button>
    </div>
  );
}

function GameOverScreen({ roundHistory, totalScore, onRestart }) {
  const maxScore = ROUNDS_PER_GAME * 1200;
  const avgGap = roundHistory.reduce((s, r) => s + r.score.gap, 0) / roundHistory.length;
  const bestRound = roundHistory.reduce((best, r) => r.score.total > best.score.total ? r : best, roundHistory[0]);
  const worstRound = roundHistory.reduce((worst, r) => r.score.total < worst.score.total ? r : worst, roundHistory[0]);
  const stars = Math.round((totalScore / maxScore) * 5);

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6 animate-fadeIn">
      <div className="text-center space-y-3">
        <Trophy size={48} className="text-yellow-400 mx-auto" />
        <h2 className="text-3xl font-bold text-white">Partie terminée !</h2>
        <div className="text-5xl font-black text-emerald-400">{formatPrice(totalScore)} pts</div>
        <div className="text-2xl">
          {Array.from({ length: 5 }).map((_, i) => (
            <span key={i} className={i < stars ? 'text-yellow-400' : 'text-gray-600'}>★</span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-800/50 rounded-xl p-4 text-center border border-gray-700">
          <p className="text-gray-400 text-xs mb-1">Écart moyen</p>
          <p className="text-xl font-bold text-white">{avgGap.toFixed(1)}%</p>
        </div>
        <div className="bg-gray-800/50 rounded-xl p-4 text-center border border-emerald-500/30">
          <p className="text-gray-400 text-xs mb-1">Meilleur round</p>
          <p className="text-xl font-bold text-emerald-400">{bestRound.score.total} pts</p>
          <p className="text-xs text-gray-500">{bestRound.apartment.city}</p>
        </div>
        <div className="bg-gray-800/50 rounded-xl p-4 text-center border border-red-500/30">
          <p className="text-gray-400 text-xs mb-1">Pire round</p>
          <p className="text-xl font-bold text-red-400">{worstRound.score.total} pts</p>
          <p className="text-xs text-gray-500">{worstRound.apartment.city}</p>
        </div>
      </div>

      <div className="bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden">
        <div className="p-3 border-b border-gray-700 text-gray-400 text-sm font-medium">
          Détail des rounds
        </div>
        <div className="max-h-[250px] overflow-y-auto">
          {roundHistory.map((r, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700/50 last:border-0">
              <div className="flex items-center gap-3">
                <span className="text-gray-500 text-sm w-6">#{r.round}</span>
                <span className="text-white text-sm">{r.apartment.city}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-sm ${r.score.gap <= 10 ? 'text-emerald-400' : r.score.gap <= 25 ? 'text-orange-400' : 'text-red-400'}`}>
                  {r.score.gap}%
                </span>
                <span className="text-white font-bold text-sm w-16 text-right">{r.score.total} pts</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={onRestart}
        className="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-4 rounded-xl transition-colors flex items-center justify-center gap-2 text-lg"
      >
        <RotateCcw size={20} />
        Rejouer
      </button>
    </div>
  );
}

function CitySelectScreen({ listings, onSelect }) {
  const metros = getAvailableMetros(listings);

  return (
    <div className="flex flex-col items-center justify-center h-full overflow-y-auto p-6 animate-fadeIn">
      <div className="w-full max-w-lg space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-white">Choisissez votre terrain de jeu</h2>
          <p className="text-gray-400 text-sm">Sélectionnez une métropole ou jouez dans toute la France</p>
        </div>

        {/* France entière */}
        <button
          onClick={() => onSelect(null)}
          className="w-full bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white font-bold py-4 px-6 rounded-xl transition-all hover:scale-[1.02] flex items-center gap-4 shadow-lg shadow-emerald-500/20"
        >
          <div className="text-3xl">🇫🇷</div>
          <div className="text-left flex-1">
            <div className="text-lg">Toute la France</div>
            <div className="text-emerald-200 text-sm font-normal">{listings.length} annonces disponibles</div>
          </div>
          <Map size={24} className="text-emerald-200" />
        </button>

        {/* Separator */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-gray-700" />
          <span className="text-gray-500 text-sm">ou une métropole</span>
          <div className="flex-1 h-px bg-gray-700" />
        </div>

        {/* Metro grid */}
        <div className="grid grid-cols-2 gap-3">
          {metros.map((metro) => (
            <button
              key={metro.key}
              onClick={() => onSelect(metro)}
              className="bg-gray-800/50 hover:bg-gray-800 border border-gray-700 hover:border-emerald-500/50 text-white py-3 px-4 rounded-xl transition-all hover:scale-[1.02] flex items-center gap-3 group"
            >
              <span className="text-2xl">{metro.emoji}</span>
              <div className="text-left flex-1 min-w-0">
                <div className="font-bold text-sm truncate group-hover:text-emerald-400 transition-colors">{metro.label}</div>
                <div className="text-gray-500 text-xs">{metro.count} annonces</div>
              </div>
            </button>
          ))}
        </div>

        {/* Back */}
        <button
          onClick={() => window.location.reload()}
          className="w-full text-gray-500 hover:text-gray-300 text-sm py-2 transition-colors"
        >
          ← Retour à l'accueil
        </button>
      </div>
    </div>
  );
}

// ============================================================
// TUTORIAL CAROUSEL
// ============================================================
const TUTORIAL_SLIDES = [
  {
    icon: Camera,
    title: 'Les photos',
    description: 'Parcourez les photos pour évaluer le standing et l\'état du bien.',
    color: 'emerald',
  },
  {
    icon: MapPin,
    title: 'La localisation',
    description: 'La carte montre le quartier : le prix varie énormément selon l\'emplacement !',
    color: 'emerald',
  },
  {
    icon: Maximize,
    title: 'Surface & pièces',
    description: 'Scrollez vers le bas pour voir la surface et le nombre de pièces !',
    color: 'emerald',
    hasBadges: true,
  },
];

function TutorialCarousel({ onAllViewed }) {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [viewedSlides, setViewedSlides] = useState(new Set([0]));
  const calledRef = useRef(false);
  const touchRef = useRef({ startX: 0, startY: 0 });

  const goToSlide = useCallback((idx) => {
    const clamped = Math.max(0, Math.min(idx, TUTORIAL_SLIDES.length - 1));
    setCurrentSlide(clamped);
    setViewedSlides((prev) => {
      const next = new Set(prev);
      next.add(clamped);
      if (next.size === TUTORIAL_SLIDES.length && !calledRef.current) {
        calledRef.current = true;
        onAllViewed();
      }
      return next;
    });
  }, [onAllViewed]);

  const prev = () => goToSlide(currentSlide - 1);
  const next = () => goToSlide(currentSlide + 1);

  const onTouchStart = (e) => {
    touchRef.current.startX = e.touches[0].clientX;
    touchRef.current.startY = e.touches[0].clientY;
  };

  const onTouchEnd = (e) => {
    const dx = e.changedTouches[0].clientX - touchRef.current.startX;
    const dy = e.changedTouches[0].clientY - touchRef.current.startY;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
      dx < 0 ? next() : prev();
    }
  };

  const slide = TUTORIAL_SLIDES[currentSlide];
  const Icon = slide.icon;

  return (
    <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700 space-y-4">
      <h3 className="text-white font-bold flex items-center gap-2 justify-center">
        <Info size={18} className="text-emerald-400" />
        Comment jouer
      </h3>

      <div
        className="relative min-h-[200px] flex items-center touch-pan-y"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* Left arrow */}
        <button
          onClick={prev}
          disabled={currentSlide === 0}
          className="absolute left-0 z-10 p-1 text-white opacity-70 hover:opacity-100 disabled:opacity-20 transition-opacity"
        >
          <ChevronLeft size={24} />
        </button>

        {/* Slide content */}
        <div className="flex-1 flex flex-col items-center text-center px-8 space-y-4 animate-fadeIn" key={currentSlide}>
          <div className="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
            <Icon size={40} className="text-emerald-400" />
          </div>

          <h4 className="text-white font-bold text-lg">{slide.title}</h4>
          <p className="text-gray-300 text-sm leading-relaxed">{slide.description}</p>

          {slide.hasBadges && (
            <div className="flex items-center gap-3 mt-1">
              <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1.5 rounded-lg border border-emerald-500/30 text-sm font-bold">
                72 m²
              </span>
              <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1.5 rounded-lg border border-emerald-500/30 text-sm font-bold">
                3 pièces
              </span>
              <ChevronDown size={20} className="text-emerald-400 animate-bounce" />
            </div>
          )}
        </div>

        {/* Right arrow */}
        <button
          onClick={next}
          disabled={currentSlide === TUTORIAL_SLIDES.length - 1}
          className="absolute right-0 z-10 p-1 text-white opacity-70 hover:opacity-100 disabled:opacity-20 transition-opacity"
        >
          <ChevronRight size={24} />
        </button>
      </div>

      {/* Dot indicators */}
      <div className="flex gap-2 justify-center">
        {TUTORIAL_SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => goToSlide(i)}
            className={`h-2 rounded-full transition-all duration-300 ${
              i === currentSlide
                ? 'bg-emerald-400 w-6'
                : viewedSlides.has(i)
                  ? 'bg-emerald-400/50 w-2'
                  : 'bg-white/30 w-2'
            }`}
          />
        ))}
      </div>
    </div>
  );
}

function WelcomeScreen({ onStart, loading }) {
  const [tutorialComplete, setTutorialComplete] = useState(false);
  const canPlay = tutorialComplete && !loading;

  return (
    <div className="flex flex-col items-center justify-center h-full overflow-y-auto p-6 animate-fadeIn">
      <div className="w-full max-w-lg space-y-8 text-center">
        <div className="space-y-3">
          <div className="text-6xl">🏠</div>
          <h1 className="text-4xl md:text-5xl font-black text-white">
            Juste<span className="text-emerald-400">Prix</span> Immo
          </h1>
          <p className="text-gray-400 text-lg">Devinez le prix des appartements en France</p>
        </div>

        <TutorialCarousel onAllViewed={() => setTutorialComplete(true)} />

        <button
          onClick={onStart}
          disabled={!canPlay}
          className={`w-full text-white font-bold py-4 px-8 rounded-xl transition-all flex items-center justify-center gap-3 text-xl ${
            canPlay
              ? 'bg-emerald-500 hover:bg-emerald-600 hover:scale-105'
              : 'bg-gray-700 cursor-not-allowed'
          }`}
        >
          {loading ? (
            <>
              <Loader2 size={24} className="animate-spin" />
              Chargement des annonces...
            </>
          ) : !tutorialComplete ? (
            <span className="text-gray-400 text-base">Parcourez le tutoriel pour commencer</span>
          ) : (
            <>
              <Play size={24} />
              Jouer
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function JustePrixImmo() {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);
  const hasSubmittedRef = useRef(false);

  // Load listings then show city selection
  const goToCitySelect = useCallback(async () => {
    setLoading(true);
    try {
      const listings = await fetchListings(50);
      dispatch({ type: 'SHOW_CITY_SELECT', listings });
    } finally {
      setLoading(false);
    }
  }, []);

  // Start game with optional metro filter
  const startGame = useCallback((metro) => {
    dispatch({ type: 'START_GAME', metro });
  }, []);

  // Timer management
  useEffect(() => {
    if (state.phase === 'playing') {
      hasSubmittedRef.current = false;
      timerRef.current = setInterval(() => {
        dispatch({ type: 'TICK' });
      }, 1000);
      return () => clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [state.phase, state.currentRound]);

  // Time up
  useEffect(() => {
    if (state.timeRemaining === 0 && state.phase === 'playing' && !hasSubmittedRef.current) {
      hasSubmittedRef.current = true;
      clearInterval(timerRef.current);
      dispatch({ type: 'TIME_UP' });
    }
  }, [state.timeRemaining, state.phase]);

  const handleSubmit = useCallback((value) => {
    if (hasSubmittedRef.current) return;
    hasSubmittedRef.current = true;
    clearInterval(timerRef.current);
    dispatch({ type: 'SUBMIT_GUESS', value });
  }, []);

  if (state.phase === 'menu') {
    return (
      <div className="h-full bg-gray-950 overflow-hidden">
        <WelcomeScreen onStart={goToCitySelect} loading={loading} />
      </div>
    );
  }

  if (state.phase === 'citySelect') {
    return (
      <div className="h-full bg-gray-950 overflow-hidden">
        <CitySelectScreen listings={state.allListings} onSelect={startGame} />
      </div>
    );
  }

  if (state.phase === 'gameover') {
    return (
      <div className="h-full bg-gray-950 p-4 flex flex-col items-center justify-center overflow-y-auto">
        <GameOverScreen
          roundHistory={state.roundHistory}
          totalScore={state.totalScore}
          onRestart={() => dispatch({ type: 'RESTART' })}
        />
      </div>
    );
  }

  const apt = state.apartments[state.currentRound];

  if (state.phase === 'result') {
    const lastRound = state.roundHistory[state.roundHistory.length - 1];
    const isLast = state.currentRound >= state.apartments.length - 1;
    return (
      <div className="h-full bg-gray-950 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-gray-900 border-b border-gray-800 px-4 py-3 shrink-0">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <h1 className="text-lg font-bold text-white">
              Juste<span className="text-emerald-400">Prix</span> Immo
            </h1>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 text-sm">
                <Award size={16} className="text-emerald-400" />
                <span className="text-white font-bold">{formatPrice(state.totalScore)} pts</span>
              </div>
              <div className="text-sm text-gray-400">
                Tour {state.currentRound + 1}/{state.apartments.length}
              </div>
            </div>
          </div>
        </div>
        <div className="flex-1 p-4 flex items-center justify-center overflow-y-auto">
          <ResultScreen roundData={lastRound} onNext={() => dispatch({ type: 'NEXT_ROUND' })} isLast={isLast} />
        </div>
      </div>
    );
  }

  // PLAYING phase
  return (
    <div className="h-full bg-gray-950 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-800 px-4 py-3 shrink-0">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <h1 className="text-lg font-bold text-white">
            Juste<span className="text-emerald-400">Prix</span> Immo
          </h1>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-sm">
              <Award size={16} className="text-emerald-400" />
              <span className="text-white font-bold">{formatPrice(state.totalScore)} pts</span>
            </div>
            <div className="text-sm text-gray-400">
              Tour {state.currentRound + 1}/{state.apartments.length}
            </div>
          </div>
        </div>
      </div>

      {/* Round dots */}
      <div className="flex justify-center gap-1.5 py-2 shrink-0">
        {state.apartments.map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-all ${
              i < state.currentRound
                ? 'bg-emerald-500'
                : i === state.currentRound
                ? 'bg-emerald-400 w-4'
                : 'bg-gray-700'
            }`}
          />
        ))}
      </div>

      {/* Main content */}
      <div className="flex-1 max-w-6xl mx-auto w-full p-4 grid grid-cols-1 lg:grid-cols-5 gap-4 overflow-y-auto touch-pan-y">
        {/* Left: Photos (3/5) */}
        <div className="lg:col-span-3 h-[300px] lg:h-auto">
          <PhotoCarousel images={apt.images} />
        </div>

        {/* Right: Map + Info (2/5) */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex-1 min-h-[200px]">
            <MapEmbed lat={apt.lat} lng={apt.lng} city={apt.city} />
          </div>
          <InfoBadges surface={apt.surface} rooms={apt.rooms} />
        </div>
      </div>

      {/* Bottom bar */}
      <div className="bg-gray-900 border-t border-gray-800 px-4 py-4 shrink-0">
        <div className="max-w-6xl mx-auto space-y-3">
          <TimerDisplay timeRemaining={state.timeRemaining} total={TIMER_SECONDS} />
          <PriceInput
            value={state.playerGuess}
            onChange={(v) => dispatch({ type: 'SET_GUESS', value: v })}
            onSubmit={handleSubmit}
            disabled={state.phase !== 'playing'}
          />
        </div>
      </div>
    </div>
  );
}
