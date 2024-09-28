import math


def get_validators(driver, gov_contract_name="gov"):

    all_validators_data = driver.items(f"{gov_contract_name}.Validators:")
    keys = list(all_validators_data.keys())
    values = list(all_validators_data.values())

    all_validators_dict = {}
    all_validators = []
    available_validator_accounts = []
    available_validators = []
    unbonding_validator_accounts = []
    unbonding_validators = []
    inactive_validator_accounts = []
    inactive_validators = []

    for i, key in enumerate(keys):
        parts = key.split(":")

        validator_account = parts[1]
        all_validators.append(validator_account)

        if validator_account not in all_validators_dict:
            all_validators_dict[validator_account] = {
                "account": validator_account,
            }
        if len(parts) == 3:
            all_validators_dict[validator_account][parts[2]] = values[i]

    all_validators = list(set(all_validators))

    for v in all_validators:
        parts = key.split(":")

        is_unbonding = all_validators_data.get(
            f"{gov_contract_name}.Validators:{v}:unbonding"
        )
        is_active = all_validators_data.get(
            f"{gov_contract_name}.Validators:{v}:active"
        )

        if is_unbonding:
            unbonding_validator_accounts.append(v)
        if not is_active:
            inactive_validator_accounts.append(v)
        if is_active and not is_unbonding:
            available_validator_accounts.append(v)

    for v in available_validator_accounts:
        available_validators.append(all_validators_dict[v])

    for v in unbonding_validator_accounts:
        unbonding_validators.append(all_validators_dict[v])

    for v in inactive_validator_accounts:
        inactive_validators.append(all_validators_dict[v])

    return available_validators, inactive_validators, unbonding_validators


def calculate_reward_percentage(
    staked_amount: float,
    staked_target: float,
    base_reward_pct: float,
    max_reward_pct: float,
    min_reward_pct: float,
    curve_steepness: float = 0.9,  # Adjusted for a more pronounced effect
) -> float:
    # TODO - Add a dynamic reward %
    return base_reward_pct