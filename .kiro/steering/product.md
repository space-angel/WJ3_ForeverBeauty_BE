# Product Overview

This is a Korean cosmetics recommendation API system that provides personalized product recommendations based on user profiles, intent tags, and safety considerations.

## Core Features

- **Personalized Recommendations**: Uses intent tags, skin type, age group, and user preferences
- **Safety Analysis**: Checks for drug interactions, allergies, and contraindications  
- **Rule-Based Engine**: Applies eligibility and scoring rules for product filtering and ranking
- **Real-time Processing**: Optimized for sub-250ms response times
- **Korean Language Support**: Designed for Korean cosmetics market with Korean text support

## Business Logic

The system follows a 6-stage recommendation pipeline:
1. Input validation and normalization
2. Candidate product retrieval based on intent tags
3. Safety evaluation (exclusion rules)
4. Suitability scoring (scoring rules)
5. Final ranking with tie-breaking algorithm
6. Result generation with detailed rationale

## Target Users

- Korean cosmetics consumers seeking personalized recommendations
- Users with specific skin concerns, allergies, or medication interactions
- Applications requiring safe, evidence-based cosmetic product suggestions