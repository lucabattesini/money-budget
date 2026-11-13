import { useEffect, useState } from "react";
import { Button, Input } from "@chakra-ui/react";
import { getAllCategories, insertNewTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { MAX_CENTS } from "../lib/money";
import customToaster from "../utils/customToaster";
import CategoryPicker from "./CategoryPicker";
import { SpinnerLoading } from "./spinnerLoading";

export default function ExpenseForm() {
    const [loading, setLoading] = useState(true)
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [selectedCategory, setSelectedCategory] = useState("");
    const [categories, setCategories] = useState([]);

    const fetchcategories = async () => {
        try {
            const token = getToken();
            const categoriesData = await getAllCategories(token)

            if (categoriesData && categoriesData.data) {
                setCategories(categoriesData.data); // the picker sorts and groups them
            }
        } catch (error) {
            console.error("Error fetching categories", error)
            customToaster("Error", "error", "Failed to load categories")
        } finally {
            setLoading(false)
        }
    };

    useEffect(() => {
        fetchcategories();
    }, []);

    const handleSubmit = () => {
        // Round, don't truncate: 19.99 * 100 is 1998.9999999999998
        const cents = Math.round(Number(value) * 100);

        if (!(cents > 0)) {
            customToaster("Error", "error", "The amount value need to be bigger than 0")
            return;
        }

        if (cents > MAX_CENTS) {
            customToaster("Error", "error", "The amount value is too big")
            return;
        }

        if (!description) {
            customToaster("Error", "error", "You need to give a description to your transaction")
            return;
        }

        if (!selectedCategory) {
            customToaster("Error", "error", "You need to select a category to your transaction")
            return;
        }

        const payload = {
            label: description,
            value: cents,
            category_id: selectedCategory
        };

        insertNewTransaction(payload, getToken())
            .then(data => {
                if (data.status === 201 || data.status === 200) {
                    customToaster("Accepted", "success", "Your transaction is saved!")

                    setvalue("");
                    setDescription("");
                    setSelectedCategory("");
                } else {
                    customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
                }
            })
    }

    if (loading) {
        return <SpinnerLoading />;
    }

    return (
        <>
            <Input 
            type="number" placeholder="Amount" variant="outline" 
            value={value} onChange={(e) => setvalue(e.target.value)}
            />

            <Input
            placeholder="Description" variant="outline" maxLength={25}
            value={description} onChange={(e) => setDescription(e.target.value)}
            />
        
            <CategoryPicker
                categories={categories}
                value={selectedCategory}
                onChange={setSelectedCategory}
                label="Select Category"
                placeholder="Select category"
            />

            <Button onClick={handleSubmit}>
                Submit
            </Button>
        </>
    );
}
