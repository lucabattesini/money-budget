import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Menu} from "@chakra-ui/react";
import { getAllCategories, insertNewTransaction } from "../api/endpoints";

export default function ReportExpense() {
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [categories, setCategories] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState("Select category");
    const [selectCategoryId, setSelectCategoryId] = useState("");

    // Do it in the other fetchs
    useEffect(() => {
        getAllCategories().then(data => setCategories(data.data))
    }, []);
    
    const handleSubmit = () => {
        const formatedValue = value * 100
        const payload = {
            label: description,
            value: parseInt(formatedValue),
            category: String(selectCategoryId)
        };
        
        insertNewTransaction(payload).then(data => {
                console.log("Successfully requested", data);
                
                setvalue("");
                setDescription("");
                setSelectedCategory("Select category");
            })
        }

    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size={"2xl"}>
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