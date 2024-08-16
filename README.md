Xian DPOS

To run tests : 

1. Setup [xian-stack](https://github.com/xian-network/xian-stack)
2. Clone this repository to `xian-stack/contracts`
3. from `xian-stack` : 
   1. `make contracting-dev-build`
   2. `make contracting-dev-shell`
4. From shell :
   1. `cd contracts/xian_dpos`
   2. `pytest`

TO-DO : 
- [x] Validator leaving / joining
- [x] Delegator leaving / joining
- [ ] Staking Epochs
- [ ] Fee Rewards
- [ ] Dynamic Inflation
- [ ] Voting
- [ ] Rules / Action Core setup
- [ ] Validator / Delegator slashing