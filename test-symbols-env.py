# test-symbols-env.py - Demo script for testing symbol management via env variables

import os
import sys
import time

# Add the app directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(current_dir, 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Import the env_manager module
import env_manager

def print_colorized(text, color_code):
    """Print text in color"""
    print(f"\033[{color_code}m{text}\033[0m")

def print_header(text):
    """Print a section header"""
    print("\n" + "=" * 60)
    print_colorized(f"  {text}", "1;36")
    print("=" * 60)

def print_success(text):
    """Print success message"""
    print_colorized(f"✓ {text}", "1;32")

def print_error(text):
    """Print error message"""
    print_colorized(f"✗ {text}", "1;31")

def print_info(text):
    """Print info message"""
    print_colorized(f"ℹ {text}", "1;34")

def run_tests():
    """Run the symbol management tests"""
    print_header("TESTING SYMBOL MANAGEMENT VIA ENV VARIABLES")
    
    # Get the initial list of symbols
    print_info("Getting initial symbol list...")
    initial_symbols = env_manager.get_available_symbols()
    print_success(f"Initial symbols: {', '.join(initial_symbols)}")
    
    # Test adding a new symbol
    print_header("ADDING NEW SYMBOLS")
    test_symbols = ["DOGEUSDT", "SOLUSDT", "AVAXUSDT"]
    
    for symbol in test_symbols:
        print_info(f"Trying to add {symbol}...")
        
        if symbol in initial_symbols:
            print_info(f"{symbol} already exists, removing it first...")
            result = env_manager.remove_symbol(symbol)
            if result:
                print_success(f"Removed {symbol} to prepare for testing")
            else:
                print_error(f"Failed to remove {symbol}")
                continue
        
        result = env_manager.add_symbol(symbol)
        if result:
            print_success(f"Added {symbol} successfully")
            
            # Verify the symbol was added
            current_symbols = env_manager.get_available_symbols()
            if symbol in current_symbols:
                print_success(f"Verified {symbol} is in the updated list")
            else:
                print_error(f"Failed to verify {symbol} in the list")
        else:
            print_error(f"Failed to add {symbol}")
    
    # Test getting the updated list
    updated_symbols = env_manager.get_available_symbols()
    print_success(f"Updated symbols: {', '.join(updated_symbols)}")
    
    # Test removing symbols
    print_header("REMOVING SYMBOLS")
    for symbol in test_symbols:
        print_info(f"Trying to remove {symbol}...")
        result = env_manager.remove_symbol(symbol)
        if result:
            print_success(f"Removed {symbol} successfully")
            
            # Verify the symbol was removed
            current_symbols = env_manager.get_available_symbols()
            if symbol not in current_symbols:
                print_success(f"Verified {symbol} is not in the updated list")
            else:
                print_error(f"Failed to verify removal of {symbol}")
        else:
            print_error(f"Failed to remove {symbol}")
    
    # Test restored list
    final_symbols = env_manager.get_available_symbols()
    print_success(f"Final symbols: {', '.join(final_symbols)}")
    
    # Test adding an invalid symbol
    print_header("TESTING INVALID SYMBOL")
    result = env_manager.add_symbol("INVALID")
    if not result:
        print_success("Failed to add invalid symbol as expected")
    else:
        print_error("Added invalid symbol, which should not happen")
    
    # Test removing the last symbol
    print_header("TESTING SAFETY CONSTRAINTS")
    if len(final_symbols) == 1:
        last_symbol = final_symbols[0]
        print_info(f"Trying to remove the last symbol {last_symbol}...")
        result = env_manager.remove_symbol(last_symbol)
        if not result:
            print_success("Failed to remove the last symbol as expected (safety constraint)")
        else:
            print_error("Removed the last symbol, which should not happen")
    
    # Ensure we have at least 2 symbols for the next test
    if len(env_manager.get_available_symbols()) < 2:
        print_info("Adding a symbol for testing...")
        env_manager.add_symbol("ETHUSDT")
    
    # Test removing all symbols except one
    current = env_manager.get_available_symbols()
    if len(current) > 1:
        print_info("Testing removing all but one symbol...")
        symbols_to_remove = current[1:]
        for symbol in symbols_to_remove:
            env_manager.remove_symbol(symbol)
        
        remaining = env_manager.get_available_symbols()
        if len(remaining) == 1:
            print_success(f"Successfully removed all but one symbol: {remaining[0]}")
        else:
            print_error(f"Expected 1 symbol, but got {len(remaining)}")
    
    # Restore symbols to their initial state
    print_header("RESTORING INITIAL STATE")
    
    # First, remove any symbols that are not in the initial list
    current = env_manager.get_available_symbols()
    for symbol in current:
        if symbol not in initial_symbols:
            print_info(f"Removing non-initial symbol {symbol}...")
            env_manager.remove_symbol(symbol)
    
    # Then, add any symbols from the initial list that are missing
    current = env_manager.get_available_symbols()
    for symbol in initial_symbols:
        if symbol not in current:
            print_info(f"Adding back initial symbol {symbol}...")
            env_manager.add_symbol(symbol)
    
    # Verify the restoration
    final_symbols = env_manager.get_available_symbols()
    print_success(f"Final restored symbols: {', '.join(final_symbols)}")
    
    if set(final_symbols) == set(initial_symbols):
        print_success("Successfully restored initial symbol state!")
    else:
        print_error("Failed to restore initial symbol state")
        print_info(f"Expected: {', '.join(sorted(initial_symbols))}")
        print_info(f"Got: {', '.join(sorted(final_symbols))}")
    
    print_header("TEST COMPLETED")

if __name__ == "__main__":
    run_tests()
