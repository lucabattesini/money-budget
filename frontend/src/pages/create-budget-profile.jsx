import React, {useState} from "react"

export default function BudgetProfile() {
    const [currentlyInvested, setCurrentlyInvested] = useState('');
    const [emergencyFound, setEmergencyFound] = useState('');
    const [checkingAccount, setCheckingAccount] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();

        const data = {
            currentlyInvested,
            emergencyFound,
            checkingAccount
        };

        try {
            const response = await fetch("", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            console.log(result)
        }   catch (error) {
            console.error("error")
        };
    }

    return(
        <div className="container">
            <h1>
                We're almost there!
            </h1>
            <h2>
                How much money do you have...
            </h2>
            <label htmlFor="name">Currently invested</label>
            <input
            id=""
            type="text"/>

            <label htmlFor="name">In your emergency found</label>
            <input
            id=""
            type="text" />

            <label htmlFor="name">In your checking account</label>
            <input
            id=""
            type="text" />

            <button className="submit">Submit</button>
        </div>
    );
}