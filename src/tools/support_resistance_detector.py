"""
Support & Resistance Detector
-----------------------------
Multi-method algorithmic S/R level detection.

Methods:
1. Swing high/low analysis
2. Volume profile (high volume nodes)
3. Fibonacci retracements
4. Psychological levels (round numbers)
5. Historical price clusters

NO manual levels - 100% algorithmic.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import Counter

from src.utils.logger import logger


@dataclass
class SupportResistanceLevel:
    """A support or resistance level."""
    
    price: float
    level_type: str  # "support" or "resistance"
    strength: str  # "weak", "moderate", "strong", "critical"
    method: str  # "swing", "volume", "fibonacci", "psychological", "cluster"
    touch_count: int  # Number of times price touched this level
    last_touch: Optional[int]  # Candle index of last touch
    zone_range: Tuple[float, float]  # Price range (zone, not exact line)
    
    def to_dict(self):
        return {
            "price": round(self.price, 2),
            "type": self.level_type,
            "strength": self.strength,
            "method": self.method,
            "touches": self.touch_count,
            "zone": (round(self.zone_range[0], 2), round(self.zone_range[1], 2))
        }


class SupportResistanceDetector:
    """
    Detect support and resistance levels using multiple methods.
    
    Combines:
    - Swing point analysis (local highs/lows)
    - Volume profile (where most trading occurred)
    - Fibonacci retracements (key ratios)
    - Psychological levels (round numbers)
    - Price clustering (frequently visited prices)
    """
    
    def __init__(self):
        self.min_touches = 2  # Minimum touches to confirm level
        self.zone_tolerance = 0.005  # 0.5% zone around level
    
    async def detect_all_levels(
        self,
        ohlcv_data: List[Dict],
        current_price: float
    ) -> Dict[str, List[SupportResistanceLevel]]:
        """
        Detect all S/R levels using multiple methods.
        
        Args:
            ohlcv_data: OHLCV data
            current_price: Current price
        
        Returns:
            Dictionary with support and resistance levels
        """
        # Extract arrays
        closes = np.array([c["close"] for c in ohlcv_data])
        highs = np.array([c["high"] for c in ohlcv_data])
        lows = np.array([c["low"] for c in ohlcv_data])
        volumes = np.array([c["volume"] for c in ohlcv_data])
        
        all_levels = []
        
        # Method 1: Swing highs/lows
        swing_levels = await self._detect_swing_levels(highs, lows, closes, volumes)
        all_levels.extend(swing_levels)
        
        # Method 2: Volume profile
        volume_levels = await self._detect_volume_levels(closes, volumes, current_price)
        all_levels.extend(volume_levels)
        
        # Method 3: Fibonacci retracements
        fib_levels = await self._detect_fibonacci_levels(highs, lows, current_price)
        all_levels.extend(fib_levels)
        
        # Method 4: Psychological levels
        psych_levels = await self._detect_psychological_levels(current_price)
        all_levels.extend(psych_levels)
        
        # Method 5: Price clusters
        cluster_levels = await self._detect_price_clusters(closes, current_price)
        all_levels.extend(cluster_levels)
        
        # Merge nearby levels and calculate strength
        merged_levels = await self._merge_levels(all_levels, current_price)
        
        # Separate into support and resistance
        supports = [l for l in merged_levels if l.price < current_price and l.level_type == "support"]
        resistances = [l for l in merged_levels if l.price > current_price and l.level_type == "resistance"]
        
        # Sort by proximity to current price
        supports.sort(key=lambda x: abs(x.price - current_price))
        resistances.sort(key=lambda x: abs(x.price - current_price))
        
        logger.info(f"📊 Detected {len(supports)} support and {len(resistances)} resistance levels")
        
        return {
            "support": supports[:5],  # Top 5 closest
            "resistance": resistances[:5]
        }
    
    async def _detect_swing_levels(self, highs, lows, closes, volumes) -> List[SupportResistanceLevel]:
        """Detect levels from swing highs and lows."""
        levels = []
        
        # Find swing highs (potential resistance)
        for i in range(5, len(highs) - 5):
            is_swing_high = all(highs[i] >= highs[i-j] and highs[i] >= highs[i+j] for j in range(1, 6))
            
            if is_swing_high:
                # Count touches
                touches = sum(1 for h in highs if abs(h - highs[i]) / highs[i] < 0.01)
                
                strength = "strong" if touches >= 3 else "moderate" if touches >= 2 else "weak"
                
                levels.append(SupportResistanceLevel(
                    price=highs[i],
                    level_type="resistance",
                    strength=strength,
                    method="swing",
                    touch_count=touches,
                    last_touch=i,
                    zone_range=(highs[i] * 0.995, highs[i] * 1.005)
                ))
        
        # Find swing lows (potential support)
        for i in range(5, len(lows) - 5):
            is_swing_low = all(lows[i] <= lows[i-j] and lows[i] <= lows[i+j] for j in range(1, 6))
            
            if is_swing_low:
                touches = sum(1 for l in lows if abs(l - lows[i]) / lows[i] < 0.01)
                strength = "strong" if touches >= 3 else "moderate" if touches >= 2 else "weak"
                
                levels.append(SupportResistanceLevel(
                    price=lows[i],
                    level_type="support",
                    strength=strength,
                    method="swing",
                    touch_count=touches,
                    last_touch=i,
                    zone_range=(lows[i] * 0.995, lows[i] * 1.005)
                ))
        
        return levels
    
    async def _detect_volume_levels(self, closes, volumes, current_price) -> List[SupportResistanceLevel]:
        """Detect levels from volume profile (high volume nodes)."""
        levels = []
        
        # Create price bins
        price_min, price_max = closes.min(), closes.max()
        num_bins = 20
        bins = np.linspace(price_min, price_max, num_bins)
        
        # Accumulate volume in each price bin
        volume_profile = np.zeros(num_bins - 1)
        
        for i, (price, vol) in enumerate(zip(closes, volumes)):
            bin_idx = np.searchsorted(bins, price) - 1
            if 0 <= bin_idx < len(volume_profile):
                volume_profile[bin_idx] += vol
        
        # Find high volume nodes (top 30%)
        threshold = np.percentile(volume_profile, 70)
        
        for i, vol in enumerate(volume_profile):
            if vol >= threshold:
                level_price = (bins[i] + bins[i+1]) / 2
                
                level_type = "support" if level_price < current_price else "resistance"
                strength = "strong" if vol > np.percentile(volume_profile, 85) else "moderate"
                
                levels.append(SupportResistanceLevel(
                    price=level_price,
                    level_type=level_type,
                    strength=strength,
                    method="volume",
                    touch_count=int(vol / volumes.mean()),
                    last_touch=None,
                    zone_range=(bins[i], bins[i+1])
                ))
        
        return levels
    
    async def _detect_fibonacci_levels(self, highs, lows, current_price) -> List[SupportResistanceLevel]:
        """Detect Fibonacci retracement levels."""
        levels = []
        
        swing_high = np.max(highs)
        swing_low = np.min(lows)
        diff = swing_high - swing_low
        
        # Standard Fibonacci ratios
        fib_ratios = {
            "0.236": 0.236,
            "0.382": 0.382,
            "0.500": 0.500,
            "0.618": 0.618,
            "0.786": 0.786
        }
        
        # Determine if uptrend or downtrend (based on current price vs swing low)
        is_uptrend = current_price > (swing_high + swing_low) / 2
        
        for name, ratio in fib_ratios.items():
            if is_uptrend:
                # Retracement from high
                fib_price = swing_high - (diff * ratio)
            else:
                # Extension from low
                fib_price = swing_low + (diff * ratio)
            
            level_type = "support" if fib_price < current_price else "resistance"
            
            levels.append(SupportResistanceLevel(
                price=fib_price,
                level_type=level_type,
                strength="moderate",
                method="fibonacci",
                touch_count=1,
                last_touch=None,
                zone_range=(fib_price * 0.998, fib_price * 1.002)
            ))
        
        return levels
    
    async def _detect_psychological_levels(self, current_price) -> List[SupportResistanceLevel]:
        """Detect psychological levels (round numbers)."""
        levels = []
        
        # Determine magnitude
        if current_price >= 10000:
            step = 1000
        elif current_price >= 1000:
            step = 500
        elif current_price >= 100:
            step = 100
        elif current_price >= 10:
            step = 10
        elif current_price >= 1:
            step = 1
        else:
            step = 0.1
        
        # Find nearby round numbers
        lower_bound = current_price * 0.9
        upper_bound = current_price * 1.1
        
        level_price = (current_price // step) * step
        
        while level_price >= lower_bound:
            if level_price < current_price:
                levels.append(SupportResistanceLevel(
                    price=level_price,
                    level_type="support",
                    strength="weak",
                    method="psychological",
                    touch_count=0,
                    last_touch=None,
                    zone_range=(level_price * 0.999, level_price * 1.001)
                ))
            level_price -= step
        
        level_price = ((current_price // step) + 1) * step
        
        while level_price <= upper_bound:
            if level_price > current_price:
                levels.append(SupportResistanceLevel(
                    price=level_price,
                    level_type="resistance",
                    strength="weak",
                    method="psychological",
                    touch_count=0,
                    last_touch=None,
                    zone_range=(level_price * 0.999, level_price * 1.001)
                ))
            level_price += step
        
        return levels[:4]  # Top 4 closest
    
    async def _detect_price_clusters(self, closes, current_price) -> List[SupportResistanceLevel]:
        """Detect price clusters (frequently visited prices)."""
        levels = []
        
        # Round prices to clusters
        if current_price >= 1000:
            rounded = np.round(closes, -1)  # Round to nearest 10
        elif current_price >= 100:
            rounded = np.round(closes, 0)  # Round to nearest 1
        else:
            rounded = np.round(closes, 2)  # Round to nearest 0.01
        
        # Count frequency
        counter = Counter(rounded)
        
        # Find most common prices (top 20%)
        threshold = np.percentile(list(counter.values()), 80)
        
        for price, count in counter.items():
            if count >= threshold:
                level_type = "support" if price < current_price else "resistance"
                strength = "strong" if count > threshold * 1.5 else "moderate"
                
                levels.append(SupportResistanceLevel(
                    price=price,
                    level_type=level_type,
                    strength=strength,
                    method="cluster",
                    touch_count=count,
                    last_touch=None,
                    zone_range=(price * 0.998, price * 1.002)
                ))
        
        return levels
    
    async def _merge_levels(
        self,
        levels: List[SupportResistanceLevel],
        current_price: float
    ) -> List[SupportResistanceLevel]:
        """
        Merge nearby levels and calculate combined strength.
        
        Args:
            levels: All detected levels
            current_price: Current price
        
        Returns:
            Merged and strengthened levels
        """
        if not levels:
            return []
        
        # Sort by price
        levels.sort(key=lambda x: x.price)
        
        merged = []
        tolerance = current_price * 0.01  # 1% tolerance
        
        i = 0
        while i < len(levels):
            current_level = levels[i]
            nearby = [current_level]
            
            # Find all nearby levels
            j = i + 1
            while j < len(levels) and abs(levels[j].price - current_level.price) <= tolerance:
                nearby.append(levels[j])
                j += 1
            
            # Merge nearby levels
            avg_price = np.mean([l.price for l in nearby])
            total_touches = sum(l.touch_count for l in nearby)
            methods = set(l.method for l in nearby)
            
            # Calculate strength based on:
            # - Number of touches
            # - Number of methods confirming
            # - Original strength
            if total_touches >= 5 or len(methods) >= 3:
                strength = "critical"
            elif total_touches >= 3 or len(methods) >= 2:
                strength = "strong"
            elif total_touches >= 2:
                strength = "moderate"
            else:
                strength = "weak"
            
            level_type = "support" if avg_price < current_price else "resistance"
            
            merged.append(SupportResistanceLevel(
                price=avg_price,
                level_type=level_type,
                strength=strength,
                method="+".join(sorted(methods)),
                touch_count=total_touches,
                last_touch=nearby[0].last_touch,
                zone_range=(avg_price * 0.995, avg_price * 1.005)
            ))
            
            i = j
        
        return merged
    
    async def calculate_level_reactions(
        self,
        levels: Dict[str, List[SupportResistanceLevel]],
        current_price: float,
        trend: str
    ) -> Dict[str, any]:
        """
        Predict price reaction at each level.
        
        Args:
            levels: Support and resistance levels
            current_price: Current price
            trend: Current trend
        
        Returns:
            Reaction predictions for each level
        """
        reactions = {
            "nearest_support": None,
            "nearest_resistance": None,
            "support_reaction": None,
            "resistance_reaction": None
        }
        
        # Find nearest levels
        if levels.get("support"):
            nearest_support = levels["support"][0]
            reactions["nearest_support"] = nearest_support.price
            
            # Predict reaction based on strength and trend
            if nearest_support.strength in ["strong", "critical"]:
                if trend == "downtrend":
                    reactions["support_reaction"] = "likely_bounce"
                else:
                    reactions["support_reaction"] = "strong_support"
            else:
                reactions["support_reaction"] = "may_break"
        
        if levels.get("resistance"):
            nearest_resistance = levels["resistance"][0]
            reactions["nearest_resistance"] = nearest_resistance.price
            
            if nearest_resistance.strength in ["strong", "critical"]:
                if trend == "uptrend":
                    reactions["resistance_reaction"] = "may_reject"
                else:
                    reactions["resistance_reaction"] = "strong_resistance"
            else:
                reactions["resistance_reaction"] = "may_break"
        
        return reactions


# ==================== GLOBAL INSTANCE ====================

def get_sr_detector() -> SupportResistanceDetector:
    """Get S/R detector instance."""
    return SupportResistanceDetector()

