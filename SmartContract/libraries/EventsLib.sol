// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

library EventsLib {
    event MerchantRegistered(
        address indexed merchant,
        uint256 indexed registeredAt,
        string businessName
    );
    event PaymentIntentCreated(
        uint256 indexed payId,
        address indexed customer,
        uint256 indexed amount,
        address merchant,
        uint256 createdAt,
        uint256 expiryTime
    );

    event TokenEnabled(address indexed _token);
    event TokenDisabled(address indexed _token);

    event Paid(
        uint256 indexed payId,
        uint256 indexed amount,
        uint256 indexed paidAt
    );
    event IntentUpdated(
        uint256 indexed payId,
        address indexed customer,
        uint256 indexed amount,
        address token,
        uint256 updatedAt
    );
}
