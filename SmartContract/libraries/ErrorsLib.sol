// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

library ErrorsLib {
    error MerchantNotRegistered();
    error InvalidAmount(uint256 actualAmount, uint256 currAmount);
    error TimePassed();
    error OnlyCustomerCanPay();
    error InvalidToken();
    // error NotEnabled();
    error AlreadyPaid();
    error InvalidTokenOrNotEnabled();
    error MerchantIsInactive();
    error AlreadyRegistered();
}
