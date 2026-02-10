"""
Input Guards - Validate and sanitize user input

Uses LLM Guard for prompt injection, toxicity, and PII detection.
"""

from typing import Tuple, List
import re


class InputGuard:
    """
    Validate user input before processing.
    
    Checks for:
    - Prompt injection attacks
    - Toxic content
    - PII that should be masked
    """
    
    def __init__(self):
        self._init_scanners()
    
    def _init_scanners(self):
        """Initialize LLM Guard scanners if available"""
        try:
            from llm_guard.input_scanners import (
                PromptInjection,
                Toxicity,
                Anonymize
            )
            
            self.prompt_injection = PromptInjection()
            self.toxicity = Toxicity(threshold=0.7)
            self.anonymize = Anonymize(
                entities=["PERSON", "EMAIL", "PHONE_NUMBER"]
            )
            self.scanners_available = True
        except ImportError:
            self.scanners_available = False
    
    def validate(self, text: str) -> Tuple[bool, str, List[str]]:
        """
        Validate input text.
        
        Args:
            text: User input to validate
            
        Returns:
            Tuple of (is_valid, sanitized_text, issues)
        """
        issues = []
        sanitized = text
        
        # Basic checks (always run)
        if len(text) > 5000:
            issues.append("input_too_long")
            sanitized = text[:5000]
        
        if len(text.strip()) < 3:
            issues.append("input_too_short")
            return False, sanitized, issues
        
        # Check for obvious prompt injection patterns
        injection_patterns = [
            r"ignore (all )?(previous |above )?instructions",
            r"disregard (all )?(previous |above )?instructions", 
            r"forget (all )?(previous |above )?instructions",
            r"you are now",
            r"pretend you are",
            r"act as if",
            r"system prompt:",
            r"<\|im_start\|>",
            r"\[INST\]",
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("prompt_injection_detected")
                return False, sanitized, issues
        
        # Use LLM Guard if available
        if self.scanners_available:
            sanitized, issues = self._run_scanners(text, issues)
        else:
            # Fallback: basic PII masking
            sanitized = self._basic_pii_mask(sanitized)
        
        is_valid = "prompt_injection_detected" not in issues and "toxic_content" not in issues
        
        return is_valid, sanitized, issues
    
    def _run_scanners(self, text: str, issues: List[str]) -> Tuple[str, List[str]]:
        """Run LLM Guard scanners"""
        from llm_guard import scan_prompt
        
        sanitized, results, is_valid = scan_prompt(
            [self.prompt_injection, self.toxicity, self.anonymize],
            text
        )
        
        for scanner_name, result in results.items():
            if not result.is_valid:
                issues.append(f"{scanner_name}_detected")
        
        return sanitized, issues
    
    def _basic_pii_mask(self, text: str) -> str:
        """Basic PII masking without LLM Guard"""
        # Email
        text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL]',
            text
        )
        
        # Phone (US format)
        text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            '[PHONE]',
            text
        )
        
        # SSN
        text = re.sub(
            r'\b\d{3}[-]?\d{2}[-]?\d{4}\b',
            '[SSN]',
            text
        )
        
        return text
