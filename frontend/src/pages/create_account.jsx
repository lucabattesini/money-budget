import react from "react";

export default function CreateAccount() {
    return (
    <div>
        <div className="container">
            <h2>
                Fill the following inputs
            </h2>

            <label htmlFor="name">Name</label>
            <input type="text" id="name" />

            <label htmlFor="email">Email</label>
            <input type="text" id="email" />

            <label htmlFor="password">Password</label>
            <input type="text" id="password" />
        </div>
        <div className="container">
            <h2>
                Create your own personalized user profile
            </h2>
            
            <label htmlFor="investment">Main Investment</label>
            <input type="text" id="name" />

            <label htmlFor="expenses">Fixed spends</label>
            <input type="text" id="email" />

            <label htmlFor="earnings">Fixed earnings</label>
            <input type="text" id="password" />
        </div>
    </div>
    );
}