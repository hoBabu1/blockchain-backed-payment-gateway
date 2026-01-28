//SPDX-License-Identifier:MIT
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
pragma solidity 0.8.20;

contract MockUsdt is ERC20 {
    constructor(
        string memory _name,
        string memory _symbol
    ) ERC20(_name, _symbol) {}

    function mint(address _to, uint256 _amount) external {
        _mint(_to, _amount);
    }
}
