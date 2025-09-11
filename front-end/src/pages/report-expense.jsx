import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Portal, Combobox, useFilter, useListCollection } from "@chakra-ui/react";
import { Toaster } from "../components/ui/toaster";
import { getAllCategories, insertNewTransaction } from "../api/endpoints";
import customToaster from "../utils/customToaster"
import { SpinnerLoading } from "../utils/loadingComponent";

export default function ReportExpense() {
    const [loading, setLoading] = useState(true)
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [categories, setCategories] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState("");
    const [filteredCategories, setFilteredCategories] = useState([]);
    const [searchQuery, setSearchQuery] = useState("")

    useEffect(() => {
        const fetchcategories = async () => {
            try {
                const categoriesData = await getAllCategories()

                if (categoriesData && categoriesData.data) {
                    const organizedCategories = categoriesData.data.map((category) => ({
                        id: category.id,
                        name: category.name,
                        value: String(category.id)
                    }));

                    setCategories(organizedCategories);
                    setFilteredCategories(organizedCategories)
                }
            } catch (error) {
                console.error("Error fetching categories", error)
                customToaster("Error", "error", "Failed to load categories")
            } finally {
                setLoading(false)
            }
        };

        fetchcategories();
    }, []);

    useEffect(() => {
        if (searchQuery.trim() === "") {
            setFilteredCategories(categories)
        } else {
            const filtered = categories.filter(category => category.name.toLowerCase().includes(searchQuery.toLowerCase())
            );
            setFilteredCategories(filtered);
        }
    }, [searchQuery, categories]);

    const handleSubmit = () => {
        const formatedValue = parseInt(value) * 100;
        const payload = {
            label: description,
            value: parseInt(formatedValue),
            category: String(selectedCategory)
        };

        if (!value || value === 0 ) {
            customToaster("Error", "error", "The amount value need to be bigger than 0")

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

        insertNewTransaction(payload)
            .then(data => {
                if (data.status === 201 || data.status === 200) {
                    customToaster("Accepted", "success", "Your transaction is saved!")

                    setvalue("");
                    setDescription("");
                    setSelectedCategory("Select category");

                } else {
                    customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
                }
            })
            .catch(error => {
                customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
            })
    }

    const handleCategorySelect = (categoryId) => {
        setSelectedCategory(categoryId);
        const selected = categories.find(category => category.value === categoryId);
        if (selected) {
            setSearchQuery(selected.name);
        }
    };

    const getDisplayValue = () => {
        if (selectedCategory) {
            const selected = categories.find(category => category.value === selectedCategory);
            return selected ? selected.name : "";
        }
        return searchQuery;
    }

    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >    
                <Toaster/>
                
                <Heading size={"2xl"}>
                    Report Expense
                </Heading>
                {loading && <SpinnerLoading/>}
                {!loading && (
                    <>
                        <Input 
                        type="number" placeholder="Amount" variant="outline" 
                        value={value} onChange={(e) => setvalue(e.target.value)}
                        />

                        <Input
                        placeholder="Description" variant="outline" maxLength={25}
                        value={description} onChange={(e) => setDescription(e.target.value)}
                        />
                    
                    
                        <Combobox.Root
                        onValueChange={({value}) => {
                            if (value.length > 0) {
                                handleCategorySelect(value[0]);
                            } else {
                                setSelectedCategory("");
                                setSearchQuery("");
                            }
                        }}
                        value={selectedCategory ? [selectedCategory] : []}
                        >
                            <Combobox.Label> Select Category </Combobox.Label>
                            <Combobox.Control>
                                <Combobox.Input 
                                placeholder="Select category"
                                defaultValue={getDisplayValue()}
                                onChange={(e) => {
                                    setSearchQuery(e.target.value);
                                    if (!e.target.value) {
                                        setSelectedCategory("");
                                    }
                                }}/>
                                <Combobox.IndicatorGroup>
                                    <Combobox.ClearTrigger
                                    onClick={() => {
                                        setSelectedCategory("");
                                        setSearchQuery("");
                                    }}/>
                                    <Combobox.Trigger />
                                </Combobox.IndicatorGroup>
                            </Combobox.Control>
                            <Portal>
                                <Combobox.Positioner>
                                    <Combobox.Content>
                                        <Combobox.Empty>No items found</Combobox.Empty>
                                        {filteredCategories.map((category) => (
                                            <Combobox.Item 
                                            item={category} 
                                            key={category.id}
                                            value={category.value}
                                            >
                                                {category.name}
                                                <Combobox.Indicator />
                                            </Combobox.Item>
                                        ))}
                                    </Combobox.Content>
                                </Combobox.Positioner>
                            </Portal>
                        </Combobox.Root>

                        <Button onClick={handleSubmit}>
                            Submit
                        </Button>
                    </>
                )}
            </Stack>
        </Center>
    );
}