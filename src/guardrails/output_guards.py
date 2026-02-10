"""
Output Guards - Validate LLM responses

Checks for hallucination, PII leakage, and compliance.
"""

from typing import Tuple, List, Dict, Any
import re


class OutputGuard:
    """
    Validate LLM output before returning to user.
    
    Checks for:
    - Hallucination (claims not in context)
    - PII in response
    - Inappropriate content
    """
    
    def __init__(self):
        self._init_scanners()
    
    def _init_scanners(self):
        """Initialize LLM Guard output scanners if available"""
        try:
            from llm_guard.output_scanners import (
                Relevance,
                Sensitive
            )
            
            self.relevance = Relevance(threshold=0.3)
            self.sensitive = Sensitive()
            self.scanners_available = True
        except ImportError:
            self.scanners_available = False
    
    def validate(
        self,
        response: str,
        context_docs: List[Dict[str, Any]]
    ) -> Tuple[bool, str, List[str]]:
        """
        Validate output response.
        
        Args:
            response: LLM response to validate
            context_docs: Source documents for grounding check
            
        Returns:
            Tuple of (is_valid, cleaned_response, issues)
        """
        issues = []
        cleaned = response
        
        # Check for empty response
        if not response or len(response.strip()) < 10:
            issues.append("empty_response")
            return False, "I couldn't generate a response.", issues
        
        # Mask any PII in response
        cleaned = self._mask_pii(cleaned)
        
        # Check for potentially harmful content patterns
        harmful_patterns = [
            r"(social security|ssn)[\s:]*\d",
            r"(credit card|card number)[\s:]*\d",
            r"(password|secret)[\s:]+\S+",
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                issues.append("sensitive_data_in_response")
                cleaned = re.sub(pattern, "[REDACTED]", cleaned, flags=re.IGNORECASE)
        
        # Use LLM Guard if available
        if self.scanners_available and context_docs:
            cleaned, issues = self._run_scanners(cleaned, context_docs, issues)
        
        is_valid = len(issues) == 0 or all(
            issue in ["pii_masked", "sensitive_data_in_response"] 
            for issue in issues
        )
        
        return is_valid, cleaned, issues
    
    def _run_scanners(
        self,
        response: str,
        context_docs: List[Dict],
        issues: List[str]
    ) -> Tuple[str, List[str]]:
        """Run LLM Guard output scanners"""
        from llm_guard import scan_output
        
        # Build context string
        context = " ".join([doc.get("content", "")[:500] for doc in context_docs[:3]])
        
        cleaned, results, is_valid = scan_output(
            [self.relevance, self.sensitive],
            context,
            response
        )
        
        for scanner_name, result in results.items():
            if not result.is_valid:
                issues.append(f"{scanner_name}_failed")
        
        return cleaned, issues
    
    def _mask_pii(self, text: str) -> str:
        """Mask any PII that might have leaked into response"""
        # Email
        text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL]',
            text
        )
        
        # Phone
        text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            '[PHONE]',
            text
        )
        
        # Credit card numbers
        text = re.sub(
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            '[CARD]',
            text
        )
        
        return text
