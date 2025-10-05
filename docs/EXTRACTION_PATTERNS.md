# Financial Advisor Extraction Patterns Documentation

This document outlines comprehensive regex patterns and extraction rules for financial advisor candidate data based on Brandon's proven email formatting standards.

## Table of Contents
- [AUM Patterns](#aum-patterns)
- [Production Metrics](#production-metrics)
- [Client Metrics](#client-metrics)
- [Performance Rankings](#performance-rankings)
- [Licenses and Certifications](#licenses-and-certifications)
- [Designations](#designations)
- [Career Progression](#career-progression)
- [Compensation Patterns](#compensation-patterns)
- [Geographic Patterns](#geographic-patterns)
- [Values and Personal Traits](#values-and-personal-traits)

## AUM Patterns

### Regex Patterns
```regex
# Standard AUM format
\$(\d+(?:\.\d+)?[BMK])(?:\s+(?:in\s+)?AUM|(?:\s+)?(?:RIA|assets?))

# Growth pattern (from X to Y)
from\s+\$(\d+(?:\.\d+)?[BMK])\s+to\s+\$(\d+(?:\.\d+)?[BMK])

# Range AUM
\$(\d+(?:\.\d+)?[BMK])[-–]?\$(\d+(?:\.\d+)?[BMK])\s+(?:in\s+)?(?:AUM|assets?)

# Managed/oversaw variations
(?:managed|oversaw|built)\s+[~]?\$(\d+(?:\.\d+)?[BMK])(?:\s+(?:in\s+)?AUM)?
```

### Real Examples from Brandon's Data
- `$2.2B RIA` → Extract: 2.2B AUM
- `$500M AUM` → Extract: 500M AUM
- `$350M AUM across 65 relationships` → Extract: 350M AUM, 65 clients
- `grew a $43M book to $72M in 2 years` → Extract: Growth from 43M to 72M
- `$10M+ in AUM from scratch` → Extract: 10M+ AUM (greenfield)
- `growing AUM from ~$150M to $720M` → Extract: Growth 150M to 720M
- `$1.5B+ in client assets` → Extract: 1.5B+ AUM

### Pattern Categories
- **Single Value**: `$X.XB/M/K AUM`
- **Growth Story**: `$X to $Y` (indicates trajectory)
- **Range**: `$X-$Y` or `$X+` (indicates minimum)
- **Context Qualifiers**: `from scratch`, `dormant book`, `built from inception`

## Production Metrics

### Regex Patterns
```regex
# Annual production
\$(\d+(?:\.\d+)?[BMK])\s+(?:annual\s+)?production

# Monthly metrics
\$(\d+(?:\.\d+)?[BMK])\s+(?:per\s+)?month

# Revenue percentages
(\d+)[-–](\d+)%\s+recurring\s+revenue

# Client acquisition rates
(\d+)\+?\s+(?:new\s+)?clients?[/\s]month
```

### Real Examples
- `annual production to ~$5M` → Extract: 5M annual production
- `65–70% recurring revenue` → Extract: 65-70% recurring revenue
- `35+ new clients/month` → Extract: 35+ monthly client acquisition

## Client Metrics

### Regex Patterns
```regex
# HNW client counts
(\d+)\s+(?:HNW|UHNW|high[- ]net[- ]worth)\s+clients?

# Total client counts
(\d+)\s+(?:relationships?|clients?)

# Client size ranges
clients?\s+(?:from\s+)?\$(\d+(?:\.\d+)?[BMK])\s+to\s+\$(\d+(?:\.\d+)?[BMK])

# Average client size
averaging\s+\$(\d+(?:\.\d+)?[BMK])[-–]\$(\d+(?:\.\d+)?[BMK])
```

### Real Examples
- `250 HNW clients` → Extract: 250 HNW clients
- `65 relationships` → Extract: 65 total clients
- `clients from $5M to $300M+` → Extract: Client range 5M-300M+
- `averaging $1M–$10M in assets` → Extract: Average client 1M-10M

## Performance Rankings

### Regex Patterns
```regex
# Ranking positions
(?:ranked\s+)?(?:#|top\s+)?(\d+)(?:[-–](\d+))?\s+nationally

# Percentile rankings
top\s+(\d+)(?:th)?\s+percentile

# Close rates and performance
(\d+)%\s+(?:vs\.?\s+(\d+)%\s+avg|close\s+rate)

# Awards and recognition
(?:President's\s+Club|Circle\s+of\s+Champions|top\s+(?:tier|producer))
```

### Real Examples
- `ranked in top tier for close rate (47% vs. 35% avg)` → Extract: 47% close rate vs 35% average
- `repeatedly ranked #1–3 nationally` → Extract: Top 1-3 national ranking
- `President's Club and Circle of Champions` → Extract: Top performer awards

## Licenses and Certifications

### Regex Patterns
```regex
# Series licenses
Series\s+(\d+)(?:,\s+(\d+))*

# Life and health insurance
(?:Life\s+(?:&|and)\s+Health|CA\s+Life\s+License)

# State-specific licenses
([A-Z]{2})\s+(?:Life\s+)?License

# License status
(?:active|inactive|formerly\s+held|can\s+be\s+reactivated)
```

### Real Examples
- `Series 7, 24, 55, 65, and 66` → Extract: Multiple series licenses
- `active Series 7, 63, and 65` → Extract: Current active licenses
- `formerly held Series 7, 24, 55, 65, and 66` → Extract: Previous licenses (reactivatable)
- `CA Life License` → Extract: State-specific license

### License Meanings Reference
- **Series 7**: General Securities Representative
- **Series 24**: General Securities Principal
- **Series 63**: Uniform Securities Agent State Law
- **Series 65**: Uniform Investment Adviser Law
- **Series 66**: Uniform Combined State Law
- **Series 55**: Equity Trader Limited Representative

## Designations

### Regex Patterns
```regex
# CFA progression
CFA\s+(?:charterholder|charter)?(?:\s+who\s+passed\s+all\s+3\s+levels\s+consecutively)?

# CFP status
CFP®?(?:\s+since\s+(\d{4}))?

# Specialized designations
(?:CPWA|CTFA|WMCP|CFA|CFP®?)

# In-progress designations
(?:currently\s+(?:completing|pursuing)|plans\s+to\s+pursue)\s+(CFA|CFP®?)
```

### Real Examples
- `CFA charterholder who passed all 3 levels consecutively` → Extract: CFA (exceptional achievement)
- `CFP® since 2000` → Extract: CFP since 2000 (long-standing)
- `currently completing CFP certification` → Extract: CFP in progress
- `Holds CPWA designation` → Extract: CPWA certified

### Designation Importance Rankings
1. **CFA**: Highest analytical credential, investment focus
2. **CFP®**: Comprehensive planning credential
3. **CPWA**: Private wealth specialization
4. **WMCP**: Wealth management focus
5. **CTFA**: Trust and fiduciary expertise

## Career Progression

### Regex Patterns
```regex
# Years of experience
(\d+)\+?\s+years?\s+(?:of\s+)?(?:experience|in\s+financial\s+services)

# Career trajectory
(?:began\s+as|started\s+as)\s+(.+?)\s+(?:and\s+progressed|progressed)

# Role transitions
transitioned\s+(?:from|into)\s+(.+?)\s+(?:to|after|into)

# Founding/building
(?:founded|built|launched)\s+(.+?)\s+from\s+(?:\$0|inception|scratch)
```

### Real Examples
- `30+ years in financial services; began as a commodities broker` → Extract: 30+ years, started as commodities broker
- `Founded and grew independent RIA from $0 to $50M AUM` → Extract: Founder, 0 to 50M growth
- `transitioned into wealth advisory after institutional trading career` → Extract: Career transition from trading

## Compensation Patterns

### Regex Patterns
```regex
# Salary ranges
desired\s+comp\s+\$(\d+(?:\.\d+)?K?)[-–]\$(\d+(?:\.\d+)?K?)\s*(?:OTE|base)?

# OTE patterns
\$(\d+(?:\.\d+)?K?)\s*OTE

# Base salary
\$(\d+(?:\.\d+)?K?)\s*base

# Complex compensation
\$(\d+(?:\.\d+)?K?)\s*[-–]\s*\$(\d+(?:\.\d+)?[KM]?)
```

### Real Examples
- `desired comp $150K-$200K OTE` → Extract: 150K-200K OTE
- `desired comp $250K base; $300K-$350K OTE` → Extract: 250K base, 300K-350K OTE
- `desired comp $750K - $1M` → Extract: 750K-1M (executive level)

## Geographic Patterns

### Regex Patterns
```regex
# Location with mobility
([^,]+,\s+[A-Z]{2})\s+\((?:Is\s+Mobile|Is\s+not\s+mobile)\)

# Remote preferences
Open\s+to\s+Remote(?:\/Hybrid)?

# Drive radius
will\s+drive\s+up\s+to\s+([\d.]+)\s+hours?\s+away

# Relocation interest
(?:strong\s+)?relocation\s+interest\s+to\s+([A-Z]+(?:\s+or\s+[A-Z]+)?)
```

### Real Examples
- `Jacksonville, FL (Is Mobile within SE/SW USA)` → Extract: Jacksonville FL, Mobile SE/SW regions
- `Orlando, FL (Is not mobile; Open to Remote/Hybrid)` → Extract: Orlando FL, Remote/Hybrid only
- `Ventura, CA (Is not mobile; will drive up to 1.5 hours away)` → Extract: Ventura CA, 1.5hr drive radius

## Values and Personal Traits

### Regex Patterns
```regex
# Values statements
Values?:\s+([^;]+(?:;[^;]+)*)

# Personal traits
(?:passionate\s+about|driven\s+by|excels\s+at|thrives\s+in)\s+([^;.]+)

# Career motivations
seeks?\s+([^;.]+?)(?:\s+(?:for|and|to))
```

### Real Examples
- `Values: honesty, sincerity, and self-awareness` → Extract: Core values
- `Values: Integrity, Growth, Advocacy` → Extract: Professional values
- `passionate about macroeconomics and portfolio construction` → Extract: Technical interests
- `seeks a "victory lap" chapter focused on high-impact leadership` → Extract: Career motivation

## Usage Guidelines

### Priority Extraction Order
1. **AUM/Assets** (highest priority - business impact)
2. **Experience Years** (seniority indicator)
3. **Licenses/Designations** (qualification verification)
4. **Client Count** (relationship management scale)
5. **Performance Metrics** (track record validation)
6. **Geographic/Mobility** (placement feasibility)
7. **Compensation** (deal structure planning)
8. **Values/Traits** (cultural fit assessment)

### Extraction Confidence Levels
- **High Confidence**: Exact dollar amounts, specific numbers, formal designations
- **Medium Confidence**: Descriptive phrases with qualifiers ("top tier", "high-performing")
- **Low Confidence**: Subjective statements, unquantified claims

### Special Handling Rules
- Always preserve growth trajectories (from X to Y)
- Flag exceptional achievements (CFA consecutive pass, national rankings)
- Capture mobility constraints as placement limiters
- Extract compensation as ranges when possible
- Preserve values statements verbatim for cultural assessment