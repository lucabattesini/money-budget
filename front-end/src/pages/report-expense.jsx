import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Menu} from "@chakra-ui/react";

export default function ReportExpense() {
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [categories, setCategories] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState("Select category");
    const [selectCategoryId, setSelectCategoryId] = useState("");

    useEffect(() => {
        fetch("http://127.0.0.1:8000/categories/", {
            method: "get"
        })
            .then(Response => Response.json())
            .then(data => setCategories(data.data))

            .catch(error => console.error("Failed to search categories", error))
    }, []);

    const handleSubmit = () => {
        const formatedValue = value * 100
        const payload = {
            label: description,
            value: parseInt(formatedValue),
            category: String(selectCategoryId)
        };

        fetch("http://127.0.0.1:8000/report-expense/", {
            method: "post",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        })
            .then(res => {
                if (!res.ok) throw new Error("Error to request");
                return res.json
            })
            .then(data => {
                console.log("Successfully requested", data);
                
                setvalue("");
                setDescription("");
                setSelectedCategory("Select category");
            })
            .catch(err => {
                console.error("Error to request", err);
            });
    };

    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="center"
            >
                <Heading>
                    Report Expense
                </Heading>

                <Input 
                type="number" placeholder="Amount" variant="outline" 
                value={value} onChange={(e) => setvalue(e.target.value)}
                />
                <Input
                placeholder="Description" variant="outline"
                value={description} onChange={(e) => setDescription(e.target.value)}
                />

                <Menu.Root>
                    <Menu.Trigger asChild>
                        <Button variant="outline"> {selectedCategory} </Button>
                    </Menu.Trigger>
                    <Menu.Content>
                        {categories?.map((category) => (
                            <Menu.Item key={category.id} 
                                onClick={() => {
                                    setSelectedCategory(category.name);
                                    setSelectCategoryId(category.id);
                                }}
                            >
                                {category.name}
                            </Menu.Item>
                        ))}
                    </Menu.Content>
                </Menu.Root>
                
                <Button onClick={handleSubmit}>Submit</Button>
            </Stack>
        </Center>
    );
}