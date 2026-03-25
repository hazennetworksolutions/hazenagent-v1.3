"""Agent nodes - LLM-first approach.

ARCHITECTURE:
- LLM handles language, intent, and formatting naturally
- Nodes provide clean data via tools
- Modern LangChain tool binding
- Zero hardcoded templates or pattern matching
"""
import time
from typing import Dict
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from src.agent.state import AgentState
from src.utils.logger import logger
from src.utils.model_factory import get_model
from config.settings import settings


# ===== HELPER FUNCTIONS =====

def extract_text_content(content) -> str:
    """Extract text from message content (handles multimodal format).
    
    Handles:
    - String: "hello"
    - List (multimodal): [{"type": "text", "text": "hello"}]
    
    Returns:
        Plain text string
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and "text" in part:
                    text_parts.append(part["text"])
                elif "content" in part:
                    text_parts.append(str(part["content"]))
            elif isinstance(part, str):
                text_parts.append(part)
        return " ".join(text_parts) if text_parts else ""
    
    return str(content) if content else ""


# ===== DEFINE TOOLS FOR LLM =====

@tool
async def get_crypto_price(symbol: str) -> str:
    """Get current price for a cryptocurrency.
    
    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH", "SOL")
    
    Returns:
        Current price and 24h change data
    """
    try:
        from src.tools.crypto_price import get_crypto_price_coingecko
        
        price_data = await get_crypto_price_coingecko(symbol.upper())
        
        if price_data and "price" in price_data:
            price = price_data['price']
            change = price_data.get('change_24h', 0)
            volume = price_data.get('volume_24h', 0)
            mcap = price_data.get('market_cap', 0)
            
            # Format with proper spacing and line breaks
            vol_b = volume / 1_000_000_000
            mcap_b = mcap / 1_000_000_000
            
            return f"""💰 {symbol.upper()} Price

Current Price: ${price:,.2f}

24h Change: {change:+.2f}% {'📈' if change >= 0 else '📉'}

24h Volume: ${vol_b:.2f}B

Market Cap: ${mcap_b:.2f}B

Source: CoinGecko (Real-Time)

⚠️ Not financial advice. DYOR."""
        
        return f"Could not fetch price for {symbol}"
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        return f"Error fetching price for {symbol}: {str(e)}"


@tool
async def analyze_chart(symbol: str, timeframe: str = "4h") -> str:
    """Analyze cryptocurrency chart with technical indicators.
    
    Enterprise-grade technical analysis with:
    - RSI, MACD, Bollinger Bands
    - Support/Resistance levels
    - Chart patterns
    - Trend analysis
    - Volume analysis
    
    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH")
        timeframe: Chart timeframe (e.g., "1h", "4h", "24h")
    
    Returns:
        Comprehensive technical analysis
    """
    try:
        from src.tools.chart_analysis import analyze_crypto_chart
        
        result = await analyze_crypto_chart(
            symbol=symbol.upper(),
            timeframe=timeframe,
            use_multi_exchange=True
        )
        
        if isinstance(result, dict) and not result.get("error"):
            # Professional enterprise format
            price = result['price']
            indicators = result['indicators']
            trend = result['trend']
            sr = result['support_resistance']
            rsi = indicators['rsi']
            macd = indicators['macd']
            bb = indicators['bollinger_bands']
            ma = indicators.get('moving_averages', {})
            patterns = result.get('patterns', [])
            summary = result.get('analysis_summary', {})
            
            # Professional format - clean and structured
            analysis = f"""{result['symbol']} Technical Analysis - {result['timeframe'].upper()}
Data Source: {result['exchange'].capitalize()} (Real-Time)

PRICE DATA
Current: ${price['current']:,.2f}
24h Change: {price['change_percent']:+.2f}%
Range: ${price['low']:,.2f} - ${price['high']:,.2f}
Volume: ${price.get('volume_avg', 0) / 1_000_000:.2f}M

TECHNICAL INDICATORS

RSI: {rsi:.1f}
• Status: {'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'}
• Signal: {'Strong Sell' if rsi > 80 else 'Sell' if rsi > 70 else 'Strong Buy' if rsi < 20 else 'Buy' if rsi < 30 else 'Hold'}

MACD:
• Histogram: {macd['histogram']:+.2f}
• Trend: {'Bullish' if macd['histogram'] > 0 else 'Bearish'}

Bollinger Bands:
• Upper: ${bb['upper']:,.2f}
• Middle: ${bb['middle']:,.2f}
• Lower: ${bb['lower']:,.2f}
• Price: {'Above middle' if price['current'] > bb['middle'] else 'Below middle'}

Moving Averages:"""
            
            # Add available MAs
            ma_list = []
            for key in ['SMA_7', 'SMA_20', 'SMA_50', 'EMA_7', 'EMA_20']:
                if key in ma:
                    ma_list.append(f"• {key}: ${ma[key]:,.2f}")
            analysis += "\n" + "\n".join(ma_list)
            
            analysis += f"""

TREND ANALYSIS
Direction: {trend['direction'].capitalize()}
Strength: {trend['strength'].capitalize()}
Sentiment: {trend['sentiment'].capitalize()}

SUPPORT & RESISTANCE"""
            
            if sr['support']:
                analysis += "\nSupport: " + ", ".join([f"${s:,.2f}" for s in sr['support'][:3]])
            if sr['resistance']:
                analysis += "\nResistance: " + ", ".join([f"${r:,.2f}" for r in sr['resistance'][:3]])
            
            if patterns:
                analysis += f"\n\nCHART PATTERNS ({len(patterns)} detected)"
                for p in patterns[:3]:
                    pname = p.get('name', 'Unknown').replace('_', ' ').title()
                    pconf = p.get('confidence', 0)
                    analysis += f"\n• {pname}: {pconf:.0f}%"
            
            # Trading bias
            bullish = summary.get('bullish_signals', 0)
            bearish = summary.get('bearish_signals', 0)
            
            if bullish > bearish:
                bias = "Bullish"
            elif bearish > bullish:
                bias = "Bearish"
            else:
                bias = "Neutral"
            
            analysis += f"""

MARKET BIAS: {bias}
Signals: {bullish} bullish, {bearish} bearish

Not financial advice. DYOR."""
            
            return analysis
            
            return analysis
        
        return f"Chart analysis unavailable for {symbol}"
    except Exception as e:
        logger.error(f"Chart analysis error: {e}")
        return f"Error analyzing {symbol}: {str(e)}"


# Bind tools to model globally
AVAILABLE_TOOLS = [get_crypto_price, analyze_chart]


# ===== AGENT NODES =====

async def tool_node(state: AgentState) -> AgentState:
    """LLM-first approach - AI decides everything.
    
    Zero regex, zero hardcoding:
    - LLM understands query naturally
    - LLM extracts coin symbols
    - LLM calls tools with correct params
    - LLM formats final response
    """
    
    if not state.get("messages"):
        return state
    
    logger.info("🤖 LLM taking control...")
    
    # Get model with tools
    model = get_model(
        model_name=settings.default_model,
        provider=settings.llm_provider,
        fast_mode=False
    )
    
    # Bind crypto tools
    model_with_tools = model.bind_tools(AVAILABLE_TOOLS)
    
    # System prompt
    from config.prompts import SYSTEM_PROMPT
    from langchain_core.messages import SystemMessage
    
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    
    # LLM decides what to do
    response = await model_with_tools.ainvoke(messages)
    
    # If LLM called tools
    if response.tool_calls:
        logger.info(f"🔧 LLM called {len(response.tool_calls)} tool(s)")
        
        from langchain_core.messages import ToolMessage
        tool_messages = []
        
        # Execute each tool
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            logger.info(f"🛠️  {tool_name}({tool_args})")
            
            # Find tool
            tool_func = next((t for t in AVAILABLE_TOOLS if t.name == tool_name), None)
            
            if tool_func:
                try:
                    result = await tool_func.ainvoke(tool_args)
                    
                    # Let LLM handle the raw result naturally
                    tool_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    ))
                    
                    logger.info(f"✅ {tool_name} executed")
                    
                except Exception as e:
                    logger.error(f"Tool error: {e}")
                    tool_messages.append(ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call["id"]
                    ))
        
        # Add tool results to state (for LLM context only)
        state["messages"].append(response)
        state["messages"].extend(tool_messages)
        
        # LLM formats final response
        messages_with_tools = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        final_response = await model.ainvoke(messages_with_tools)
        
        # Clean up: Remove intermediate tool messages (keep only final response)
        # Pop tool messages and intermediate AI message
        for _ in range(len(tool_messages) + 1):
            if state["messages"]:
                state["messages"].pop()
        
        # Add only the final formatted response (extract text)
        final_text = extract_text_content(final_response.content)
        state["messages"].append(AIMessage(content=final_text))
        logger.info("✅ LLM formatted final response")
    
    else:
        # No tools - direct response
        # Extract text from response (handle multimodal format)
        response_text = extract_text_content(response.content)
        state["messages"].append(AIMessage(content=response_text))
        logger.info("✅ Direct response (no tools)")
    
    return state


