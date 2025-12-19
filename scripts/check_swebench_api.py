#!/usr/bin/env python3
"""
Diagnostic script to check what's available in the SWE-bench API.
Run this if you encounter import errors.
"""

try:
    import swebench
    print(f"✓ swebench imported successfully")
    print(f"  Version: {getattr(swebench, '__version__', 'unknown')}")
except ImportError as e:
    print(f"✗ Failed to import swebench: {e}")
    exit(1)

try:
    import swebench.harness
    print(f"✓ swebench.harness imported successfully")
    print(f"  Available: {[x for x in dir(swebench.harness) if not x.startswith('_')]}")
except ImportError as e:
    print(f"✗ Failed to import swebench.harness: {e}")

try:
    import swebench.harness.run_evaluation as run_eval
    print(f"✓ swebench.harness.run_evaluation imported successfully")
    print(f"  Available functions/classes: {[x for x in dir(run_eval) if not x.startswith('_')]}")
    
    # Check for callable items
    callables = [x for x in dir(run_eval) 
                 if not x.startswith('_') and callable(getattr(run_eval, x, None))]
    print(f"  Callable items: {callables}")
    
    # Try to find evaluation function
    for name in ['run_evaluation', 'evaluate', 'evaluate_instances', 'run']:
        if hasattr(run_eval, name):
            func = getattr(run_eval, name)
            if callable(func):
                print(f"  ✓ Found potential evaluation function: {name}")
                print(f"    Type: {type(func)}")
                if hasattr(func, '__doc__') and func.__doc__:
                    print(f"    Doc: {func.__doc__[:100]}...")
except ImportError as e:
    print(f"✗ Failed to import swebench.harness.run_evaluation: {e}")
except Exception as e:
    print(f"✗ Error inspecting swebench.harness.run_evaluation: {e}")

print("\nTo fix import issues:")
print("1. Check your SWE-bench version: pip show swebench")
print("2. Update if needed: pip install --upgrade swebench>=4.0.4")
print("3. Check SWE-bench documentation for API changes")

