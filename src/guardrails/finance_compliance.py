"""
Finance Compliance Guard - Domain-specific safety rules

Enforces finance-specific compliance requirements.
"""

import re
from typing import List


class FinanceComplianceGuard:
    """
    Finance domain-specific compliance guardrails.
    
    Ensures responses don't:
    - Provide specific investment advice
    - Make guarantees about returns
    - Contain prohibited financial claims
    """
    
    # Phrases that indicate investment advice
    INVESTMENT_ADVICE_PATTERNS = [
        r"you should (buy|sell|invest in)",
        r"i recommend (buying|selling|investing)",
        r"guaranteed (returns|profit)",
        r"risk[- ]free investment",
        r"can't lose",
        r"double your money",
        r"insider (tip|information)",
        r"hot stock",
        r"get rich quick",
    ]
    
    # Required disclaimer for financial content
    DISCLAIMER = (
        "\n\n---\n"
        "*Disclaimer: This information is for educational purposes only and "
        "does not constitute financial, investment, or legal advice. "
        "Past performance does not guarantee future results. "
        "Please consult a qualified financial advisor for personalized guidance.*"
    )
    
    def process_response(self, response: str) -> str:
        """
        Process response to ensure finance compliance.
        
        Args:
            response: LLM response to process
            
        Returns:
            Compliant response with appropriate disclaimers
        """
        # Check for investment advice patterns
        has_financial_content = self._has_financial_content(response)
        has_advice = self._has_investment_advice(response)
        
        if has_advice:
            # Add warning about the advice
            response = self._add_advice_warning(response)
        
        if has_financial_content:
            # Add standard disclaimer
            response = self._add_disclaimer(response)
        
        # Redact account numbers
        response = self._redact_financial_identifiers(response)
        
        return response
    
    def _has_financial_content(self, text: str) -> bool:
        """Check if response contains financial content"""
        financial_keywords = [
            "invest", "stock", "bond", "fund", "portfolio",
            "dividend", "return", "profit", "loss", "trading",
            "market", "asset", "equity", "revenue", "earnings"
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in financial_keywords)
    
    def _has_investment_advice(self, text: str) -> bool:
        """Check if response contains investment advice"""
        text_lower = text.lower()
        
        for pattern in self.INVESTMENT_ADVICE_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _add_advice_warning(self, response: str) -> str:
        """Add warning when investment advice is detected"""
        warning = (
            "\n\n> ⚠️ **Important**: The above should not be interpreted as "
            "investment advice. Always conduct your own research and consult "
            "with a licensed financial advisor before making investment decisions.\n"
        )
        return response + warning
    
    def _add_disclaimer(self, response: str) -> str:
        """Add standard financial disclaimer"""
        if self.DISCLAIMER not in response:
            return response + self.DISCLAIMER
        return response
    
    def _redact_financial_identifiers(self, text: str) -> str:
        """Redact account numbers and financial identifiers"""
        # Credit card numbers
        text = re.sub(
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            '[CARD-REDACTED]',
            text
        )
        
        # Account numbers (generic long numbers)
        text = re.sub(
            r'\b\d{9,12}\b',
            '[ACCOUNT-REDACTED]',
            text
        )
        
        # Routing numbers
        text = re.sub(
            r'\b\d{9}\b(?=.*routing)',
            '[ROUTING-REDACTED]',
            text,
            flags=re.IGNORECASE
        )
        
        return text
    
    def validate_no_advice(self, response: str) -> List[str]:
        """Check for investment advice violations"""
        violations = []
        text_lower = response.lower()
        
        for pattern in self.INVESTMENT_ADVICE_PATTERNS:
            if re.search(pattern, text_lower):
                violations.append(f"investment_advice: {pattern}")
        
        return violations
